"""Feed Radar routes."""
from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request

from database import get_db, row_to_dict, rows_to_dicts, utc_now
from middleware.auth import require_auth
from services.feeds import FeedError, add_feed, refresh_feeds

logger = logging.getLogger(__name__)

feeds_bp = Blueprint("feeds", __name__)


@feeds_bp.route("", methods=["GET"])
@require_auth
def list_feeds():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT f.*,
               COUNT(CASE WHEN i.status = 'new' THEN 1 END) AS new_item_count
        FROM feeds f
        LEFT JOIN feed_items i ON i.feed_id = f.id AND i.user_id = f.user_id
        WHERE f.user_id = ?
        GROUP BY f.id
        ORDER BY lower(f.title), f.created_at DESC
        """,
        (g.user.id,),
    ).fetchall()
    return jsonify({"feeds": rows_to_dicts(rows)})


@feeds_bp.route("", methods=["POST"])
@require_auth
def create_feed():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    conn = get_db()
    try:
        feed = add_feed(conn, g.user.id, url)
        conn.commit()
        return jsonify(feed), 201
    except FeedError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        conn.rollback()
        return jsonify({"error": f"Failed to add feed: {str(exc)}"}), 500


@feeds_bp.route("/<feed_id>", methods=["DELETE"])
@require_auth
def delete_feed(feed_id: str):
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM feeds WHERE id = ? AND user_id = ?",
        (feed_id, g.user.id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return jsonify({"error": "Feed not found"}), 404
    return jsonify({"success": True})


@feeds_bp.route("/refresh", methods=["POST"])
@require_auth
def refresh():
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))
    stale_after_minutes = data.get("stale_after_minutes", 30)
    try:
        stale_after_minutes = max(1, min(int(stale_after_minutes), 1440))
    except (TypeError, ValueError):
        stale_after_minutes = 30

    conn = get_db()
    result = refresh_feeds(
        conn,
        g.user.id,
        force=force,
        stale_after_minutes=stale_after_minutes,
    )
    conn.commit()
    return jsonify(result)


@feeds_bp.route("/inbox", methods=["GET"])
@require_auth
def inbox():
    limit = min(request.args.get("limit", 50, type=int), 100)
    offset = request.args.get("offset", 0, type=int)
    feed_id = request.args.get("feed_id")
    feed_filter = "AND i.feed_id = ?" if feed_id else ""
    params = [g.user.id]
    count_params = [g.user.id]
    if feed_id:
        params.append(feed_id)
        count_params.append(feed_id)
    params.extend([limit, offset])
    conn = get_db()
    rows = conn.execute(
        f"""
        SELECT i.*, f.title AS feed_title, f.site_url AS feed_site_url, f.favicon_url AS feed_favicon_url
        FROM feed_items i
        JOIN feeds f ON f.id = i.feed_id AND f.user_id = i.user_id
        LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
        WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
        {feed_filter}
        ORDER BY COALESCE(i.published_at, i.first_seen_at) DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()
    total = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM feed_items i
        LEFT JOIN bookmarks b ON b.user_id = i.user_id AND b.url = i.url
        WHERE i.user_id = ? AND i.status = 'new' AND b.id IS NULL
        {feed_filter}
        """,
        count_params,
    ).fetchone()["total"]
    return jsonify({"items": rows_to_dicts(rows), "total": total})


@feeds_bp.route("/items/<item_id>/dismiss", methods=["POST"])
@require_auth
def dismiss_item(item_id: str):
    conn = get_db()
    cursor = conn.execute(
        """
        UPDATE feed_items
        SET status = 'dismissed', updated_at = ?
        WHERE id = ? AND user_id = ? AND status = 'new'
        """,
        (utc_now(), item_id, g.user.id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return jsonify({"error": "Feed item not found"}), 404
    return jsonify({"success": True})


@feeds_bp.route("/items/<item_id>/saved", methods=["POST"])
@require_auth
def mark_item_saved(item_id: str):
    data = request.get_json() or {}
    bookmark_id = data.get("bookmark_id")
    if not bookmark_id:
        return jsonify({"error": "bookmark_id is required"}), 400

    conn = get_db()
    bookmark = conn.execute(
        "SELECT id FROM bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, g.user.id),
    ).fetchone()
    if not bookmark:
        return jsonify({"error": "Bookmark not found"}), 404

    cursor = conn.execute(
        """
        UPDATE feed_items
        SET status = 'saved', bookmark_id = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (bookmark_id, utc_now(), item_id, g.user.id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return jsonify({"error": "Feed item not found"}), 404
    item = conn.execute(
        "SELECT * FROM feed_items WHERE id = ? AND user_id = ?",
        (item_id, g.user.id),
    ).fetchone()
    return jsonify(row_to_dict(item))


@feeds_bp.route("/items/<item_id>/content", methods=["GET"])
@require_auth
def get_item_content(item_id: str):
    fetch_clean = request.args.get("fetch_clean", "false").lower() == "true"
    conn = get_db()
    row = conn.execute(
        "SELECT id, url, content, content_format FROM feed_items WHERE id = ? AND user_id = ?",
        (item_id, g.user.id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Feed item not found"}), 404

    item = row_to_dict(row)
    url = item["url"]

    if fetch_clean or not item.get("content"):
        try:
            from services.content_extractor import ContentExtractor
            extracted = ContentExtractor.extract(url)
            content = extracted.get("content")
            if content and content.strip():
                content_format = extracted.get("content_format") or "markdown"
                conn.execute(
                    "UPDATE feed_items SET content = ?, content_format = ?, updated_at = ? WHERE id = ?",
                    (content, content_format, utc_now(), item_id),
                )
                conn.commit()
                item["content"] = content
                item["content_format"] = content_format
            elif not item.get("content"):
                summary_row = conn.execute("SELECT summary FROM feed_items WHERE id = ?", (item_id,)).fetchone()
                if summary_row and summary_row["summary"]:
                    item["content"] = summary_row["summary"]
                    item["content_format"] = "html"
        except Exception as exc:
            logger.error(f"Failed to extract item content for {url}: {exc}")
            if not item.get("content"):
                return jsonify({"error": f"Failed to extract content: {str(exc)}"}), 500

    return jsonify({
        "content": item.get("content"),
        "content_format": item.get("content_format") or "html"
    })
