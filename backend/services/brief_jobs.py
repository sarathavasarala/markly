"""Persistent background jobs for scheduled daily brief generation."""
from __future__ import annotations

import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from config import Config, Prompts
from database import db_session, new_id, utc_now
from services import signal_pipeline

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
LEASE_DURATION = timedelta(minutes=30)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="brief-jobs")
_worker_lock = threading.Lock()
_worker_running = False


def enqueue_daily_brief_jobs() -> dict[str, int]:
    """Create at most one scheduled brief job per user for the current UTC day."""
    now = utc_now()
    run_date = now[:10]
    queued = 0
    existing = 0

    with db_session() as conn:
        users = conn.execute("SELECT id FROM users").fetchall()
        for user in users:
            cursor = conn.execute(
                """
                INSERT INTO brief_jobs (
                    id, user_id, run_date, status, attempts, available_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', 0, ?, ?, ?)
                ON CONFLICT(user_id, run_date) DO NOTHING
                """,
                (new_id(), user["id"], run_date, now, now, now),
            )
            if cursor.rowcount:
                queued += 1
            else:
                existing += 1

    return {"queued": queued, "existing": existing}


def start_worker() -> None:
    """Start one local worker to drain persisted jobs without blocking a request."""
    global _worker_running
    with _worker_lock:
        if _worker_running:
            return
        _worker_running = True
    _executor.submit(_drain_jobs)


def _drain_jobs() -> None:
    global _worker_running
    try:
        while True:
            job = _claim_next_job()
            if job:
                _run_job(job)
                continue

            retry_delay = _next_retry_delay()
            if retry_delay is None:
                break
            threading.Event().wait(retry_delay)
    except Exception:
        logger.exception("Brief job worker stopped unexpectedly.")
    finally:
        with _worker_lock:
            _worker_running = False


def _next_retry_delay() -> float | None:
    """Return the wait time for the next retry or an expired running-job lease."""
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT status, available_at, started_at
            FROM brief_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY CASE status WHEN 'queued' THEN available_at ELSE started_at END
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None

    if row["status"] == "queued":
        available_at = datetime.fromisoformat(row["available_at"])
    else:
        available_at = datetime.fromisoformat(row["started_at"]) + LEASE_DURATION
    return max(0, (available_at - now).total_seconds())


def _claim_next_job() -> dict[str, Any] | None:
    """Atomically claim the next queued job, including jobs abandoned by a restart."""
    now = datetime.now(timezone.utc)
    now_text = now.isoformat()
    lease_expires_before = (now - LEASE_DURATION).isoformat()

    with db_session() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT id, user_id, attempts
            FROM brief_jobs
            WHERE (status = 'queued' AND available_at <= ?)
               OR (status = 'running' AND started_at <= ?)
            ORDER BY created_at
            LIMIT 1
            """,
            (now_text, lease_expires_before),
        ).fetchone()
        if not row:
            return None

        conn.execute(
            """
            UPDATE brief_jobs
            SET status = 'running',
                attempts = attempts + 1,
                started_at = ?,
                updated_at = ?,
                error_message = NULL
            WHERE id = ?
            """,
            (now_text, now_text, row["id"]),
        )
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "attempts": row["attempts"] + 1,
        }


def _run_job(job: dict[str, Any]) -> None:
    try:
        result = _generate_brief(job["user_id"])
    except Exception as exc:
        logger.exception("Scheduled brief job %s failed.", job["id"])
        _record_failure(job, exc)
        return

    now = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            UPDATE brief_jobs
            SET status = ?,
                brief_id = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (result["status"], result.get("brief_id"), now, now, job["id"]),
        )


def _generate_brief(user_id: str) -> dict[str, Any]:
    """Run the existing daily brief pipeline outside the cron HTTP request."""
    with db_session() as conn:
        settings = signal_pipeline.load_user_settings(
            conn,
            user_id,
            default_filter_template=Prompts.FILTER_PROMPT_TEMPLATE,
            default_planning_template=Prompts.PLANNING_PROMPT_TEMPLATE,
            default_synthesis_template=Prompts.SYNTHESIS_PROMPT_TEMPLATE,
        )
        items = signal_pipeline.select_candidates(
            conn,
            user_id,
            settings["candidate_limit"],
            taste_profile=settings["taste_profile"],
        )

    if not items:
        return {"status": "skipped"}

    selected_items = signal_pipeline.llm_filter(
        items,
        settings["taste_profile"],
        settings["filter_template"],
        synthesis_limit=settings.get("synthesis_limit"),
    )
    if not selected_items:
        return {"status": "skipped"}

    updates = signal_pipeline.run_extract_contents(selected_items)
    with db_session() as conn:
        signal_pipeline.persist_content_updates(conn, updates)

    brief_plan = ""
    if settings["planning_enabled"]:
        brief_plan = signal_pipeline.plan_brief(
            selected_items,
            settings["taste_profile"],
            settings["planning_template"],
            recent_briefs=settings.get("recent_briefs", ""),
        )

    research_brief, _ = signal_pipeline.research(
        selected_items,
        web_search_enabled=settings["web_search_enabled"],
        brief_plan=brief_plan,
        taste_profile=settings["taste_profile"],
    )
    content = signal_pipeline.synthesize(
        selected_items,
        settings["taste_profile"],
        settings["synthesis_template"],
        research_brief=research_brief,
        recent_briefs=settings.get("recent_briefs", ""),
        brief_plan=brief_plan,
    )
    if Config.SIGNAL_HUMANIZER_ENABLED:
        content = signal_pipeline.style_edit_brief(content, Prompts.HUMANIZER_PROMPT_TEMPLATE)

    with db_session() as conn:
        brief = signal_pipeline.save_brief(conn, user_id, content, selected_items)

    return {"status": "succeeded", "brief_id": brief["id"]}


def _record_failure(job: dict[str, Any], exc: Exception) -> None:
    now = datetime.now(timezone.utc)
    now_text = now.isoformat()
    error_message = str(exc)
    retry_at = (now + timedelta(minutes=2 ** job["attempts"])).isoformat()

    with db_session() as conn:
        if job["attempts"] >= MAX_ATTEMPTS:
            conn.execute(
                """
                UPDATE brief_jobs
                SET status = 'failed',
                    error_message = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (error_message, now_text, now_text, job["id"]),
            )
        else:
            conn.execute(
                """
                UPDATE brief_jobs
                SET status = 'queued',
                    available_at = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (retry_at, error_message, now_text, job["id"]),
            )

        conn.execute(
            """
            INSERT INTO telemetry_logs (id, user_id, stage, error_message, traceback, created_at)
            VALUES (?, ?, 'scheduled-brief-generation', ?, ?, ?)
            """,
            (new_id(), job["user_id"], error_message, traceback.format_exc(), now_text),
        )
