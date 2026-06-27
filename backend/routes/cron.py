"""Cron and background task routes."""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from database import db_session
from services.feeds import refresh_feeds, embed_pending_feed_items_async
from services import signal_pipeline, hn_synthesis
from config import Config, Prompts

logger = logging.getLogger(__name__)

cron_bp = Blueprint("cron", __name__)


def _authenticate_cron() -> bool:
    """Validate Bearer token against CRON_SECRET env variable."""
    cron_secret = Config.CRON_SECRET
    if not cron_secret:
        logger.warning("CRON_SECRET environment variable is not set. Rejecting cron request.")
        return False

    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {cron_secret}"
    return auth_header == expected


@cron_bp.route("/refresh", methods=["POST"])
def cron_refresh():
    """Trigger feed refreshes and asynchronous embedding generation for all users."""
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with db_session() as conn:
            users = conn.execute("SELECT id, email FROM users").fetchall()
    except Exception as exc:
        logger.exception("Failed to query users from database during cron refresh.")
        return jsonify({"error": f"Database error: {str(exc)}"}), 500

    results = {}
    for user in users:
        user_id = user["id"]
        email = user["email"]
        try:
            # Refresh feeds
            with db_session() as conn:
                res = refresh_feeds(conn, user_id, force=False, stale_after_minutes=30)
            
            # Queue background embedding generation if items were added
            if res.get("items_added", 0) > 0:
                embed_pending_feed_items_async(user_id)
                
            results[email] = {
                "status": "success",
                "summary": res
            }
        except Exception as exc:
            logger.exception("Failed to refresh feeds for user %s (%s)", user_id, email)
            results[email] = {
                "status": "failed",
                "error": str(exc)
            }

    return jsonify({"success": True, "results": results})


@cron_bp.route("/brief", methods=["POST"])
def cron_brief():
    """Trigger daily brief synthesis for all users."""
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with db_session() as conn:
            users = conn.execute("SELECT id, email FROM users").fetchall()
    except Exception as exc:
        logger.exception("Failed to query users from database during cron brief generation.")
        return jsonify({"error": f"Database error: {str(exc)}"}), 500

    results = {}
    for user in users:
        user_id = user["id"]
        email = user["email"]
        try:
            # 1. Load user settings
            with db_session() as conn:
                settings = signal_pipeline.load_user_settings(
                    conn,
                    user_id,
                    default_filter_template=Prompts.FILTER_PROMPT_TEMPLATE,
                    default_planning_template=Prompts.PLANNING_PROMPT_TEMPLATE,
                    default_synthesis_template=Prompts.SYNTHESIS_PROMPT_TEMPLATE,
                )
                taste_profile = settings["taste_profile"]
                candidate_limit = settings["candidate_limit"]
                filter_template = settings["filter_template"]
                planning_template = settings["planning_template"]
                planning_enabled = settings["planning_enabled"]
                synthesis_template = settings["synthesis_template"]
                web_search_enabled = settings["web_search_enabled"]

                # 2. Select candidates
                items = signal_pipeline.select_candidates(
                    conn, user_id, candidate_limit, taste_profile=taste_profile
                )

            if not items:
                results[email] = {
                    "status": "skipped",
                    "reason": "no_candidates",
                    "message": "No recent feed items found."
                }
                continue

            # 3. LLM Filter
            selected_items = signal_pipeline.llm_filter(
                items, taste_profile, filter_template, synthesis_limit=settings.get("synthesis_limit")
            )
            if not selected_items:
                results[email] = {
                    "status": "skipped",
                    "reason": "no_high_signal_content",
                    "message": "No items matched the taste profile."
                }
                continue

            # 4. Extract full content in parallel
            updates = signal_pipeline.run_extract_contents(selected_items)
            with db_session() as conn:
                signal_pipeline.persist_content_updates(conn, updates)

            # 5. Plan, research, and synthesize report (model calls)
            brief_plan = ""
            if planning_enabled:
                brief_plan = signal_pipeline.plan_brief(
                    selected_items,
                    taste_profile,
                    planning_template,
                    recent_briefs=settings.get("recent_briefs", ""),
                )
            research_brief, _ = signal_pipeline.research(
                selected_items,
                web_search_enabled=web_search_enabled,
                brief_plan=brief_plan,
                taste_profile=taste_profile,
            )
            content = signal_pipeline.synthesize(
                selected_items,
                taste_profile,
                synthesis_template,
                research_brief=research_brief,
                recent_briefs=settings.get("recent_briefs", ""),
                brief_plan=brief_plan,
            )

            # 5b. Tone and style pass (humanizer) to strip AI writing patterns
            if Config.SIGNAL_HUMANIZER_ENABLED:
                content = signal_pipeline.style_edit_brief(
                    content, Prompts.HUMANIZER_PROMPT_TEMPLATE
                )

            # 6. Save final brief
            with db_session() as conn:
                brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)

            results[email] = {
                "status": "success",
                "brief_id": brief["id"],
                "articles_count": len(selected_items)
            }
        except Exception as exc:
            logger.exception("Failed to generate brief for user %s (%s)", user_id, email)
            results[email] = {
                "status": "failed",
                "error": str(exc)
            }

    return jsonify({"success": True, "results": results})


@cron_bp.route("/hn-synthesis", methods=["POST"])
def cron_hn_synthesis():
    """Trigger HN synthesis pipeline: fetch frontpage, classify, synthesize, fan out to feed_items."""
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with db_session() as conn:
            summary = hn_synthesis.run_hn_synthesis(conn)
        return jsonify({"success": True, "summary": summary})
    except Exception as exc:
        logger.exception("HN synthesis cron failed")
        return jsonify({"error": str(exc)}), 500
