"""Public profile and subscription routes."""
from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from database import (
    get_db,
    get_user_by_username,
    new_id,
    row_to_dict,
    utc_now,
)
from middleware.auth import current_user_optional, require_auth

logger = logging.getLogger(__name__)
public_bp = Blueprint("public", __name__)


def get_user_profile_by_username(username: str) -> dict | None:
    """Get local user profile info from username."""
    user = get_user_by_username(username)
    if not user:
        return None
    count = get_db().execute(
        "SELECT COUNT(*) AS count FROM bookmarks WHERE user_id = ? AND is_public = 1",
        (user["id"],),
    ).fetchone()["count"]
    return {
        "id": user["id"],
        "email": user["email"],
        "avatar_url": user.get("avatar_url"),
        "full_name": user.get("full_name"),
        "bookmark_count": count,
    }


@public_bp.route("/@<username>/tags", methods=["GET"])
def get_public_tags(username: str):
    """Get top public tags for a curator."""
    profile = get_user_profile_by_username(username)
    if not profile:
        return jsonify({"error": "User not found"}), 404
    limit = min(request.args.get("limit", 20, type=int), 100)

    try:
        rows = get_db().execute(
            """
            SELECT j.value AS tag, COUNT(*) AS count
            FROM bookmarks, json_each(bookmarks.auto_tags) AS j
            WHERE user_id = ? AND is_public = 1 AND auto_tags IS NOT NULL
            GROUP BY j.value
            ORDER BY count DESC
            LIMIT ?
            """,
            (profile["id"], limit),
        ).fetchall()
        tags = [{"tag": row["tag"], "count": row["count"]} for row in rows]
        return jsonify({"tags": tags})
    except Exception as e:
        logger.error(f"Error fetching public tags for {username}: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@public_bp.route("/@<username>/bookmarks", methods=["GET"])
def get_public_bookmarks(username: str):
    """Get public bookmarks for a user's public profile."""
    profile = get_user_profile_by_username(username)
    if not profile:
        return jsonify({"error": "User not found"}), 404

    viewer = current_user_optional()
    is_owner = bool(viewer and viewer.id == profile["id"])
    visibility_clause = "" if is_owner else "AND is_public = 1"

    try:
        total_count = get_db().execute(
            f"SELECT COUNT(*) AS count FROM bookmarks WHERE user_id = ? {visibility_clause}",
            (profile["id"],),
        ).fetchone()["count"]
        rows = get_db().execute(
            f"""
            SELECT id, url, original_title, clean_title, user_description, ai_summary,
                   auto_tags, domain, favicon_url, created_at, is_public
            FROM bookmarks
            WHERE user_id = ? {visibility_clause}
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (profile["id"],),
        ).fetchall()
        bookmarks = [row_to_dict(row) for row in rows]

        viewer_urls = set()
        if viewer and not is_owner:
            saved_rows = get_db().execute(
                "SELECT url FROM bookmarks WHERE user_id = ?",
                (viewer.id,),
            ).fetchall()
            viewer_urls = {row["url"] for row in saved_rows}

        for bookmark in bookmarks:
            bookmark["is_saved_by_viewer"] = bookmark["url"] in viewer_urls

        return jsonify({
            "bookmarks": bookmarks,
            "total_count": total_count,
            "username": username,
            "is_owner": is_owner,
            "profile": {
                "avatar_url": profile.get("avatar_url"),
                "full_name": profile.get("full_name"),
            },
        })
    except Exception as e:
        logger.error(f"Error fetching public bookmarks for {username}: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@public_bp.route("/@<username>/subscribe", methods=["POST"])
def subscribe_to_curator(username: str):
    """Subscribe to a curator's digest."""
    data = request.get_json() or {}
    email = data.get("email", "").lower().strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO subscribers (id, curator_username, email, subscribed_at)
            VALUES (?, ?, ?, ?)
            """,
            (new_id(), username.lower(), email, utc_now()),
        )
        conn.commit()
        return jsonify({"success": True, "message": "Subscribed successfully"})
    except Exception as e:
        conn.rollback()
        error_msg = str(e)
        if "UNIQUE" in error_msg.upper():
            return jsonify({"error": "Already subscribed"}), 409
        logger.error(f"Subscribe error: {e}")
        return jsonify({"error": "Failed to subscribe"}), 500


@public_bp.route("/@<username>/subscribers/count", methods=["GET"])
def get_subscriber_count(username: str):
    """Get subscriber count for a curator."""
    try:
        count = get_db().execute(
            """
            SELECT COUNT(*) AS count
            FROM subscribers
            WHERE curator_username = ? AND unsubscribed_at IS NULL
            """,
            (username.lower(),),
        ).fetchone()["count"]
        return jsonify({"count": count})
    except Exception as e:
        logger.error(f"Error getting subscriber count: {e}")
        return jsonify({"count": 0})


def _is_profile_owner(username: str) -> bool:
    user_email = getattr(g.user, "email", None)
    if user_email and user_email.split("@")[0].lower() == username.lower():
        return True
    profile = get_user_profile_by_username(username)
    return bool(profile and profile["id"] == g.user.id)


@public_bp.route("/@<username>/subscribers", methods=["GET"])
@require_auth
def list_subscribers(username: str):
    """List subscribers for a curator (owner only)."""
    if not _is_profile_owner(username):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        rows = get_db().execute(
            """
            SELECT email, subscribed_at
            FROM subscribers
            WHERE curator_username = ? AND unsubscribed_at IS NULL
            ORDER BY subscribed_at DESC
            """,
            (username.lower(),),
        ).fetchall()
        return jsonify({"subscribers": [dict(row) for row in rows]})
    except Exception as e:
        logger.error(f"Error listing subscribers for {username}: {str(e)}")
        return jsonify({"error": f"Failed to list subscribers: {str(e)}"}), 500


@public_bp.route("/@<username>/subscription/check", methods=["GET"])
@require_auth
def check_subscription(username: str):
    """Check if the current user is subscribed to this curator."""
    user_email = getattr(g.user, "email", None)
    if not user_email:
        return jsonify({"is_subscribed": False})
    row = get_db().execute(
        """
        SELECT id FROM subscribers
        WHERE curator_username = ? AND email = ? AND unsubscribed_at IS NULL
        """,
        (username.lower(), user_email.lower()),
    ).fetchone()
    return jsonify({"is_subscribed": bool(row)})


@public_bp.route("/@<username>/unsubscribe", methods=["POST"])
def unsubscribe_from_curator(username: str):
    """Unsubscribe from a curator's digest."""
    data = request.get_json() or {}
    email = data.get("email", "").lower().strip()
    if not email:
        viewer = current_user_optional()
        email = getattr(viewer, "email", "").lower().strip() if viewer else ""
    if not email:
        return jsonify({"error": "Email required to unsubscribe"}), 400

    conn = get_db()
    try:
        conn.execute(
            """
            UPDATE subscribers
            SET unsubscribed_at = ?
            WHERE curator_username = ? AND email = ?
            """,
            (utc_now(), username.lower(), email),
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        logger.error(f"Unsubscribe error: {e}")
        return jsonify({"error": "Failed to unsubscribe"}), 500


@public_bp.route("/@<username>/subscribers/<subscriber_email>", methods=["DELETE"])
@require_auth
def delete_subscriber(username: str, subscriber_email: str):
    """Delete a subscriber from your list (owner only)."""
    if not _is_profile_owner(username):
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM subscribers WHERE curator_username = ? AND email = ?",
            (username.lower(), subscriber_email.lower()),
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting subscriber {subscriber_email}: {e}")
        return jsonify({"error": "Failed to delete subscriber"}), 500


@public_bp.route("/account", methods=["DELETE"])
@require_auth
def delete_account():
    """Completely delete the user's account and all data."""
    user_id = g.user.id
    user_email = g.user.email
    username = user_email.split("@")[0].lower()
    conn = get_db()
    try:
        conn.execute("DELETE FROM subscribers WHERE curator_username = ?", (username,))
        conn.execute("DELETE FROM subscribers WHERE email = ?", (user_email,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Account and all data deleted"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting account for {user_id}: {e}")
        return jsonify({"error": f"Failed to delete account: {str(e)}"}), 500


@public_bp.route("/bookmarks/<bookmark_id>/visibility", methods=["PATCH"])
@require_auth
def toggle_bookmark_visibility(bookmark_id: str):
    """Toggle a bookmark's public/private status."""
    data = request.get_json() or {}
    is_public = bool(data.get("is_public", True))
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            UPDATE bookmarks
            SET is_public = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (1 if is_public else 0, utc_now(), bookmark_id, g.user.id),
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Bookmark not found or access denied"}), 404
        conn.commit()
        return jsonify({"success": True, "is_public": is_public})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating visibility for bookmark {bookmark_id}: {e}")
        return jsonify({"error": f"Failed to update visibility: {str(e)}"}), 500
