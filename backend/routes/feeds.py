"""Feed Radar routes."""
from __future__ import annotations

import logging
from flask import Blueprint, g, jsonify, request

from database import get_db, row_to_dict, rows_to_dicts, utc_now
from middleware.auth import require_auth
from services.feeds import FeedError, add_feed, embed_pending_feed_items_async, refresh_feeds

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
        embed_pending_feed_items_async(g.user.id)
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
    if result.get("items_added"):
        embed_pending_feed_items_async(g.user.id)
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
    
    # Join feed_items with feeds to get parent feed_url, summary, and current content fields
    row = conn.execute(
        """
        SELECT i.id, i.url, i.content, i.content_format, i.summary, f.feed_url 
        FROM feed_items i
        JOIN feeds f ON i.feed_id = f.id
        WHERE i.id = ? AND i.user_id = ?
        """,
        (item_id, g.user.id),
    ).fetchone()
    
    if not row:
        return jsonify({"error": "Feed item not found"}), 404

    item = row_to_dict(row)
    url = item["url"]
    feed_url = item.get("feed_url")
    summary = item.get("summary")
    content = item.get("content")
    content_format = item.get("content_format")

    from services.feeds import should_bypass_entry_content
    bypass_jina = should_bypass_entry_content(feed_url)

    def _get_fallback_content(sum_text: str | None) -> str:
        note = "<p><em>Note: Full-text extraction failed after 3 attempts. Displaying feed summary fallback.</em></p>"
        if sum_text and sum_text.strip():
            return f"{note}\n{sum_text.strip()}"
        return f"{note}\n<p>No summary available for this item.</p>"

    # Check for permanent failure state
    if content_format == "failed_3" and not fetch_clean:
        if not content or "extraction failed" not in content:
            fallback = _get_fallback_content(summary)
            conn.execute(
                "UPDATE feed_items SET content = ?, content_format = 'html', updated_at = ? WHERE id = ?",
                (fallback, utc_now(), item_id),
            )
            conn.commit()
            content = fallback
            content_format = "html"
        return jsonify({
            "content": content,
            "content_format": content_format
        })

    # Track failures (failed_1, failed_2, failed_3)
    current_failures = 0
    if fetch_clean:
        current_failures = 0
    elif content_format and content_format.startswith("failed_"):
        try:
            current_failures = int(content_format.split("_")[1])
        except (IndexError, ValueError):
            current_failures = 0

    if fetch_clean or not content or (content_format and content_format.startswith("failed_")):
        try:
            from services.content_extractor import ContentExtractor
            if bypass_jina:
                extracted = ContentExtractor.extract(url, bypass_jina=True)
            else:
                extracted = ContentExtractor.extract(url)
            extracted_content = extracted.get("content")
            
            if extracted_content and extracted_content.strip():
                extracted_format = extracted.get("content_format") or "markdown"
                conn.execute(
                    "UPDATE feed_items SET content = ?, content_format = ?, updated_at = ? WHERE id = ?",
                    (extracted_content, extracted_format, utc_now(), item_id),
                )
                conn.commit()
                content = extracted_content
                content_format = extracted_format
            else:
                raise ValueError("Extractor returned empty content")
        except Exception as exc:
            logger.error(f"Failed to extract item content for {url}: {exc}")
            next_failures = current_failures + 1
            if next_failures >= 3:
                fallback = _get_fallback_content(summary)
                conn.execute(
                    "UPDATE feed_items SET content = ?, content_format = 'html', updated_at = ? WHERE id = ?",
                    (fallback, utc_now(), item_id),
                )
                conn.commit()
                content = fallback
                content_format = "html"
                return jsonify({
                    "content": content,
                    "content_format": content_format
                })
            else:
                conn.execute(
                    "UPDATE feed_items SET content_format = ?, updated_at = ? WHERE id = ?",
                    (f"failed_{next_failures}", utc_now(), item_id),
                )
                conn.commit()
                return jsonify({"error": f"Failed to extract content (attempt {next_failures}/3): {str(exc)}"}), 500

    return jsonify({
        "content": content,
        "content_format": content_format or "html"
    })
