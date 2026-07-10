"""Cron and background task routes."""
from __future__ import annotations

import logging
from flask import Blueprint, jsonify, request

from database import db_session
from services.feeds import refresh_feeds, embed_pending_feed_items_async
from services import brief_jobs, hn_synthesis
from config import Config

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
    """Queue daily brief generation and return before the work begins."""
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        summary = brief_jobs.enqueue_daily_brief_jobs()
        brief_jobs.start_worker()
    except Exception as exc:
        logger.exception("Failed to queue scheduled brief jobs.")
        return jsonify({"error": f"Failed to queue brief jobs: {str(exc)}"}), 500

    return jsonify({"success": True, "status": "queued", **summary}), 202


@cron_bp.route("/hn-synthesis", methods=["POST"])
def cron_hn_synthesis():
    """Trigger HN synthesis pipeline: fetch frontpage, classify, synthesize, fan out to feed_items."""
    if not _authenticate_cron():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with db_session() as conn:
            summary = hn_synthesis.run_hn_synthesis(conn)
        return jsonify({"success": True, "summary": summary})
    except hn_synthesis.HNFrontpageUnavailable as exc:
        logger.error("HN synthesis has no available front-page source: %s", exc)
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        logger.exception("HN synthesis cron failed")
        return jsonify({"error": str(exc)}), 500
