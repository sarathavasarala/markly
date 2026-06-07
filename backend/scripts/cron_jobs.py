#!/usr/bin/env python
"""CLI cron execution script for Markly feed refreshes and daily brief synthesis.

Can be run on a single periodic scheduler (e.g. every 30 minutes). Checks schedule.yaml
and database timestamps to execute tasks when they are due.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import logging
from zoneinfo import ZoneInfo
import yaml

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_session, utc_now  # noqa: E402
from services.feeds import refresh_feeds, _embed_pending_feed_items  # noqa: E402
from services import signal_pipeline  # noqa: E402
from routes.signal import FILTER_PROMPT_TEMPLATE, SYNTHESIS_PROMPT_TEMPLATE  # noqa: E402
from services.email_service import EmailService  # noqa: E402

# Setup basic logging to stdout for cron logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("cron_jobs")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schedule.yaml")


def load_schedule_config() -> dict:
    """Load the schedule.yaml configuration."""
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Configuration file %s not found. Using defaults.", CONFIG_PATH)
        return {
            "schedule": {
                "feed_refresh_interval_hours": 12,
                "daily_brief_time": "05:30",
                "timezone": "Asia/Kolkata"
            },
            "email": {
                "enable_delivery": False
            }
        }
    with open(CONFIG_PATH, "r") as f:
        try:
            return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error("Failed to parse schedule.yaml: %s. Using defaults.", exc)
            return {
                "schedule": {
                    "feed_refresh_interval_hours": 12,
                    "daily_brief_time": "05:30",
                    "timezone": "Asia/Kolkata"
                },
                "email": {
                    "enable_delivery": False
                }
            }


def parse_time_str(time_str: str) -> tuple[int, int]:
    """Parse HH:MM string into hour and minute integers."""
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except Exception:
        logger.warning("Invalid time format '%s', defaulting to 05:30", time_str)
        return 5, 30


def run_feed_refresh(user_id: str, username: str) -> bool:
    """Run feeds refresh and pending items embedding synchronously."""
    logger.info("[%s] Refreshing feeds...", username)
    try:
        with db_session() as conn:
            result = refresh_feeds(conn, user_id, force=False, stale_after_minutes=30)
            logger.info(
                "[%s] Refresh finished: Checked: %s, Skpped: %s, Unchanged: %s, Added: %s, Failed: %s",
                username,
                result.get("feeds_checked"),
                result.get("feeds_skipped"),
                result.get("feeds_unchanged"),
                result.get("items_added"),
                result.get("feeds_failed")
            )
            # Synchronously update the last refresh timestamp
            conn.execute(
                "UPDATE users SET last_feed_refresh_at = ?, updated_at = ? WHERE id = ?",
                (utc_now(), utc_now(), user_id)
            )
        
        # Synchronously embed pending feed items (runs in script context)
        logger.info("[%s] Embedding pending feed items...", username)
        _embed_pending_feed_items(user_id)
        logger.info("[%s] Embedding task complete.", username)
        return True
    except Exception as exc:
        logger.exception("[%s] Feed refresh failed", username)
        return False


def run_daily_brief(user_id: str, username: str, user_email: str, full_name: str | None, email_enabled: bool) -> bool:
    """Run candidate selection, LLM filtering, full text extraction, synthesis, and email delivery."""
    logger.info("[%s] Generating daily brief...", username)
    try:
        with db_session() as conn:
            settings = signal_pipeline.load_user_settings(
                conn,
                user_id,
                default_filter_template=FILTER_PROMPT_TEMPLATE,
                default_synthesis_template=SYNTHESIS_PROMPT_TEMPLATE,
            )
            taste_profile = settings["taste_profile"]

            # 1. Candidate selection
            items = signal_pipeline.select_candidates(
                conn, user_id, settings["candidate_limit"], taste_profile=taste_profile
            )
            if not items:
                logger.info("[%s] No recent feed content available to brief.", username)
                # Still update timestamp so we don't spam checking empty queues every hour
                conn.execute(
                    "UPDATE users SET last_brief_generated_at = ?, updated_at = ? WHERE id = ?",
                    (utc_now(), utc_now(), user_id)
                )
                return True

            # 2. LLM filter
            selected_items = signal_pipeline.llm_filter(items, taste_profile, settings["filter_template"])
            if not selected_items:
                logger.info("[%s] No high-signal feed content matching taste profile.", username)
                conn.execute(
                    "UPDATE users SET last_brief_generated_at = ?, updated_at = ? WHERE id = ?",
                    (utc_now(), utc_now(), user_id)
                )
                return True

            # 3. Content extraction (synchronous in CLI context)
            logger.info("[%s] Extracting full article text for %s items...", username, len(selected_items))
            updates = signal_pipeline.run_extract_contents(selected_items)
            signal_pipeline.persist_content_updates(conn, updates)

            # 4. Synthesize brief
            logger.info("[%s] Synthesizing brief memo...", username)
            content = signal_pipeline.synthesize(
                selected_items,
                taste_profile,
                settings["synthesis_template"],
                web_search_enabled=settings["web_search_enabled"],
            )

            # 5. Persist brief
            brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)
            logger.info("[%s] Daily brief successfully saved (ID: %s).", username, brief["id"])

            # 6. Update the last run timestamp in database
            conn.execute(
                "UPDATE users SET last_brief_generated_at = ?, updated_at = ? WHERE id = ?",
                (utc_now(), utc_now(), user_id)
            )

        # 7. Deliver via email if configured
        if email_enabled:
            logger.info("[%s] Dispatching brief to %s via SMTP...", username, user_email)
            sent = EmailService.send_brief(user_email, content, full_name)
            if sent:
                logger.info("[%s] Email brief delivered successfully.", username)
            else:
                logger.warning("[%s] Email brief delivery failed.", username)
        else:
            logger.info("[%s] Email delivery is disabled. Skipping dispatch.", username)

        return True
    except Exception as exc:
        logger.exception("[%s] Daily brief generation failed", username)
        return False


def check_and_run(args):
    """Core logic to check schedule criteria and run scheduled tasks."""
    config = load_schedule_config()
    schedule_cfg = config.get("schedule", {})
    email_cfg = config.get("email", {})
    
    interval_hours = float(schedule_cfg.get("feed_refresh_interval_hours", 12))
    brief_time_str = schedule_cfg.get("daily_brief_time", "05:30")
    tz_name = schedule_cfg.get("timezone", "Asia/Kolkata")
    email_enabled = bool(email_cfg.get("enable_delivery", False))

    logger.info("Starting scheduler check (Timezone: %s)", tz_name)
    logger.info("Settings: Refresh Feed: every %s hrs | Daily Brief: %s | Email Enabled: %s", 
                interval_hours, brief_time_str, email_enabled)

    # Localize current time
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        logger.error("Invalid timezone '%s': %s. Falling back to UTC.", tz_name, exc)
        tz = ZoneInfo("UTC")

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone(tz)
    
    # Parse brief target hour and minute
    target_hour, target_minute = parse_time_str(brief_time_str)
    brief_target_today = now_local.replace(
        hour=target_hour, minute=target_minute, second=0, microsecond=0
    )

    with db_session() as conn:
        users = conn.execute(
            "SELECT id, username, email, full_name, last_feed_refresh_at, last_brief_generated_at FROM users"
        ).fetchall()

    if not users:
        logger.info("No users found in database. Nothing to process.")
        return

    for user in users:
        user_id = user["id"]
        username = user["username"]
        email = user["email"]
        full_name = user["full_name"]
        
        logger.info("Evaluating user '%s' (%s)", username, email)

        # ----------------------------------------------------
        # 1. CHECK FEED REFRESH SCHEDULE
        # ----------------------------------------------------
        should_refresh = False
        if args.force_refresh:
            should_refresh = True
            logger.info("[%s] Force-refresh flag is set.", username)
        elif not user["last_feed_refresh_at"]:
            should_refresh = True
            logger.info("[%s] No record of prior feed refresh. Due now.", username)
        else:
            try:
                last_refresh = datetime.datetime.fromisoformat(user["last_feed_refresh_at"])
                # Ensure last_refresh is timezone aware in UTC
                if last_refresh.tzinfo is None:
                    last_refresh = last_refresh.replace(tzinfo=datetime.timezone.utc)
                
                elapsed = now_utc - last_refresh
                due_delta = datetime.timedelta(hours=interval_hours)
                if elapsed >= due_delta:
                    should_refresh = True
                    logger.info("[%s] Feed refresh due. Last refreshed: %s (%s hours ago).", 
                                username, last_refresh.isoformat(), round(elapsed.total_seconds() / 3600.0, 2))
                else:
                    logger.info("[%s] Feed refresh not due yet. Last refreshed: %s (%s hours ago).", 
                                username, last_refresh.isoformat(), round(elapsed.total_seconds() / 3600.0, 2))
            except Exception as exc:
                logger.error("[%s] Error parsing last_feed_refresh_at timestamp: %s. Forcing run.", username, exc)
                should_refresh = True

        if should_refresh:
            if args.dry_run:
                logger.info("[DRY-RUN] Would run feed refresh for %s", username)
            else:
                run_feed_refresh(user_id, username)

        # ----------------------------------------------------
        # 2. CHECK DAILY BRIEF SCHEDULE
        # ----------------------------------------------------
        should_brief = False
        if args.force_brief:
            should_brief = True
            logger.info("[%s] Force-brief flag is set.", username)
        elif now_local < brief_target_today:
            # We haven't reached the brief generation time today yet
            logger.info("[%s] Daily brief time (%s) not reached today yet. Current local time: %s", 
                        username, brief_time_str, now_local.strftime("%H:%M:%S"))
        else:
            # We are at or past the target briefing time today
            if not user["last_brief_generated_at"]:
                should_brief = True
                logger.info("[%s] No record of prior briefing. Due now.", username)
            else:
                try:
                    last_brief = datetime.datetime.fromisoformat(user["last_brief_generated_at"])
                    if last_brief.tzinfo is None:
                        last_brief = last_brief.replace(tzinfo=datetime.timezone.utc)
                    
                    # Convert last brief time to the user's localized timezone
                    last_brief_local = last_brief.astimezone(tz)
                    
                    # If the last briefing occurred before today's target hour/minute local time, we owe them a brief!
                    if last_brief_local < brief_target_today:
                        should_brief = True
                        logger.info("[%s] Briefing due today. Last briefing: %s (before target %s).", 
                                    username, last_brief_local.isoformat(), brief_target_today.isoformat())
                    else:
                        logger.info("[%s] Briefing already generated today. Last briefing: %s (after target %s).", 
                                    username, last_brief_local.isoformat(), brief_target_today.isoformat())
                except Exception as exc:
                    logger.error("[%s] Error parsing last_brief_generated_at timestamp: %s. Forcing run.", username, exc)
                    should_brief = True

        if should_brief:
            if args.dry_run:
                logger.info("[DRY-RUN] Would generate daily brief and send email to %s", username)
            else:
                run_daily_brief(user_id, username, email, full_name, email_enabled)


def main():
    parser = argparse.ArgumentParser(description="Stateful cron processor for Markly feed reader.")
    parser.add_argument("--force-refresh", action="store_true", help="Force run RSS feed fetches immediately.")
    parser.add_argument("--force-brief", action="store_true", help="Force run daily brief generation immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Check schedules and print actions without executing.")
    args = parser.parse_args()
    
    try:
        check_and_run(args)
    except Exception as e:
        logger.exception("Cron manager failed unexpectedly")
        sys.exit(1)


if __name__ == "__main__":
    main()
