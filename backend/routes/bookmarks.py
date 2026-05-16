"""Bookmark routes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import validators
from flask import Blueprint, g, jsonify, request

from database import (
    get_db,
    new_id,
    refresh_bookmark_fts,
    row_to_dict,
    serialize_record,
    utc_now,
)
from middleware.auth import require_auth
from services.enrichment import analyze_link, enrich_bookmark_async, retry_failed_enrichment

logger = logging.getLogger(__name__)
bookmarks_bp = Blueprint("bookmarks", __name__)


BOOKMARK_COLUMNS = (
    "id, user_id, url, domain, original_title, favicon_url, thumbnail_url, raw_notes, "
    "user_description, clean_title, ai_summary, content_extract, key_quotes, auto_tags, "
    "intent_type, technical_level, content_type, embedding, created_at, updated_at, "
    "last_accessed_at, access_count, enrichment_status, enrichment_error, is_public, "
    "folder_id, suggested_folder_name"
)


def _bookmark_response(row, *, include_embedding: bool = False):
    bookmark = row_to_dict(row)
    if bookmark and not include_embedding:
        bookmark.pop("embedding", None)
    return bookmark


def _insert_bookmark(conn, data: dict):
    now = utc_now()
    record = {
        "id": data.get("id") or new_id(),
        "created_at": data.get("created_at") or now,
        "updated_at": data.get("updated_at") or now,
        "access_count": data.get("access_count", 0),
        "is_public": data.get("is_public", True),
        "auto_tags": data.get("auto_tags", []),
        "key_quotes": data.get("key_quotes", []),
        **data,
    }
    serialized = serialize_record(record)
    columns = ", ".join(serialized.keys())
    placeholders = ", ".join("?" for _ in serialized)
    conn.execute(
        f"INSERT INTO bookmarks ({columns}) VALUES ({placeholders})",
        tuple(serialized.values()),
    )
    refresh_bookmark_fts(conn, record["id"])
    return conn.execute(f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE id = ?", (record["id"],)).fetchone()


def _update_bookmark(conn, bookmark_id: str, user_id: str | None, data: dict):
    update_data = serialize_record({**data, "updated_at": utc_now()})
    assignments = ", ".join(f"{key} = ?" for key in update_data.keys())
    params = list(update_data.values()) + [bookmark_id]
    where = "id = ?"
    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)
    conn.execute(f"UPDATE bookmarks SET {assignments} WHERE {where}", params)
    refresh_bookmark_fts(conn, bookmark_id)
    return conn.execute(
        f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE id = ?"
        + (" AND user_id = ?" if user_id else ""),
        (bookmark_id, user_id) if user_id else (bookmark_id,),
    ).fetchone()


@bookmarks_bp.route("/analyze", methods=["POST"])
@require_auth
def analyze_bookmark():
    """Analyze a URL synchronously without creating a database record."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data["url"].strip()
    if not validators.url(url):
        return jsonify({"error": "Invalid URL format"}), 400

    user_notes = data.get("notes", "").strip() or None
    use_nano_model = bool(data.get("use_nano_model", False))

    try:
        extracted, enriched = analyze_link(url, user_notes=user_notes, use_nano_model=use_nano_model)
        return jsonify({
            "url": url,
            "domain": extracted.get("domain"),
            "original_title": extracted.get("title") or url,
            "favicon_url": extracted.get("favicon_url"),
            "thumbnail_url": extracted.get("thumbnail_url"),
            "clean_title": enriched.get("clean_title"),
            "ai_summary": enriched.get("ai_summary"),
            "auto_tags": enriched.get("auto_tags", []),
            "content_type": enriched.get("content_type"),
            "intent_type": enriched.get("intent_type"),
            "technical_level": enriched.get("technical_level"),
            "scrape_success": bool(extracted.get("content")),
        })
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return jsonify({"error": f"Failed to analyze link: {str(e)}"}), 500


@bookmarks_bp.route("", methods=["POST"])
@require_auth
def create_bookmark():
    """Create a new bookmark."""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data["url"].strip()
    if not validators.url(url):
        return jsonify({"error": "Invalid URL format"}), 400

    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
    except Exception:
        domain = None

    raw_notes = data.get("notes", "").strip() or None
    user_description = data.get("description", "").strip() or None
    is_pre_enriched = all(k in data for k in ["clean_title", "ai_summary", "auto_tags"])
    conn = get_db()

    try:
        existing = conn.execute(
            f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE user_id = ? AND url = ?",
            (g.user.id, url),
        ).fetchone()
        if existing:
            return jsonify({
                "message": "Bookmark already exists",
                "bookmark": _bookmark_response(existing),
                "already_exists": True,
            })

        if is_pre_enriched:
            bookmark_data = {
                "user_id": g.user.id,
                "url": url,
                "domain": data.get("domain") or domain,
                "original_title": data.get("original_title") or url,
                "clean_title": data.get("clean_title"),
                "ai_summary": data.get("ai_summary"),
                "auto_tags": data.get("auto_tags", []),
                "favicon_url": data.get("favicon_url"),
                "thumbnail_url": data.get("thumbnail_url"),
                "content_type": data.get("content_type"),
                "intent_type": data.get("intent_type"),
                "technical_level": data.get("technical_level"),
                "raw_notes": raw_notes,
                "user_description": user_description,
                "enrichment_status": "completed",
                "is_public": True,
            }
        else:
            if user_description:
                first_line = user_description.split("\n")[0][:100].strip()
                original_title = first_line if first_line else url
            else:
                original_title = url

            from services.content_extractor import ContentExtractor
            favicon_url = ContentExtractor.extract_favicon(url)
            bookmark_data = {
                "user_id": g.user.id,
                "url": url,
                "domain": domain,
                "original_title": original_title,
                "clean_title": original_title,
                "favicon_url": favicon_url,
                "thumbnail_url": None,
                "raw_notes": raw_notes,
                "user_description": user_description,
                "enrichment_status": "pending",
                "is_public": True,
                "folder_id": data.get("folder_id"),
            }

        row = _insert_bookmark(conn, bookmark_data)
        conn.commit()
        bookmark = _bookmark_response(row)

        if not is_pre_enriched:
            enrich_bookmark_async(bookmark["id"])
        else:
            from services.enrichment import generate_embedding_async
            generate_embedding_async(bookmark["id"], bookmark)

        return jsonify(bookmark), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to create bookmark: {str(e)}"}), 500


@bookmarks_bp.route("", methods=["GET"])
@require_auth
def list_bookmarks():
    """List bookmarks with optional filtering and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    offset = (page - 1) * per_page
    domain = request.args.get("domain")
    content_type = request.args.get("content_type")
    intent_type = request.args.get("intent_type")
    tags = request.args.getlist("tag")
    status = request.args.get("status")
    folder_id = request.args.get("folder_id")
    sort_by = request.args.get("sort", "created_at")
    sort_order = request.args.get("order", "desc")
    allowed_sort = {"created_at", "updated_at", "clean_title", "domain", "access_count"}
    sort_by = sort_by if sort_by in allowed_sort else "created_at"
    direction = "ASC" if sort_order == "asc" else "DESC"

    clauses = ["user_id = ?"]
    params: list = [g.user.id]
    if domain:
        clauses.append("domain = ?")
        params.append(domain)
    if content_type:
        clauses.append("content_type = ?")
        params.append(content_type)
    if intent_type:
        clauses.append("intent_type = ?")
        params.append(intent_type)
    if status:
        clauses.append("enrichment_status = ?")
        params.append(status)
    if folder_id:
        if folder_id == "unfiled":
            clauses.append("folder_id IS NULL")
        else:
            clauses.append("folder_id = ?")
            params.append(folder_id)
    for tag in tags:
        clauses.append("auto_tags LIKE ?")
        params.append(f"%{tag}%")

    where = " AND ".join(clauses)
    conn = get_db()
    try:
        total = conn.execute(f"SELECT COUNT(*) AS count FROM bookmarks WHERE {where}", params).fetchone()["count"]
        rows = conn.execute(
            f"""
            SELECT {BOOKMARK_COLUMNS}
            FROM bookmarks
            WHERE {where}
            ORDER BY {sort_by} {direction}
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()
        bookmarks = [_bookmark_response(row) for row in rows]
        pages = (total + per_page - 1) // per_page
        return jsonify({
            "bookmarks": bookmarks,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to list bookmarks: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>", methods=["DELETE"])
@require_auth
def delete_bookmark(bookmark_id: str):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM bookmarks WHERE id = ? AND user_id = ?",
            (bookmark_id, g.user.id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Bookmark not found"}), 404
        conn.execute("DELETE FROM bookmarks_fts WHERE bookmark_id = ?", (bookmark_id,))
        conn.execute("DELETE FROM bookmarks WHERE id = ? AND user_id = ?", (bookmark_id, g.user.id))
        conn.commit()
        return jsonify({"message": "Bookmark deleted successfully"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to delete bookmark: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>/access", methods=["POST"])
@require_auth
def track_access(bookmark_id: str):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT access_count FROM bookmarks WHERE id = ? AND user_id = ?",
            (bookmark_id, g.user.id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Bookmark not found"}), 404
        current_count = row["access_count"] or 0
        conn.execute(
            """
            UPDATE bookmarks
            SET access_count = ?, last_accessed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (current_count + 1, datetime.now(timezone.utc).isoformat(), utc_now(), bookmark_id, g.user.id),
        )
        conn.commit()
        return jsonify({"access_count": current_count + 1})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to track access: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>/retry", methods=["POST"])
@require_auth
def retry_enrichment(bookmark_id: str):
    row = get_db().execute(
        "SELECT enrichment_status FROM bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, g.user.id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Bookmark not found"}), 404
    retry_failed_enrichment(bookmark_id)
    return jsonify({"message": "Enrichment retry started"})


@bookmarks_bp.route("/<bookmark_id>", methods=["PATCH"])
@require_auth
def update_bookmark(bookmark_id: str):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed_fields = [
        "clean_title", "ai_summary", "auto_tags", "raw_notes",
        "user_description", "content_type", "intent_type", "technical_level",
        "thumbnail_url", "folder_id", "is_public",
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    conn = get_db()
    try:
        row = _update_bookmark(conn, bookmark_id, g.user.id, update_data)
        if not row:
            return jsonify({"error": "Bookmark not found"}), 404
        conn.commit()
        return jsonify(_bookmark_response(row))
    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Failed to update bookmark: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>", methods=["GET"])
@require_auth
def get_bookmark(bookmark_id: str):
    row = get_db().execute(
        f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, g.user.id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Bookmark not found"}), 404
    return jsonify(_bookmark_response(row))


@bookmarks_bp.route("/save-public", methods=["POST"])
@require_auth
def save_public_bookmark():
    """Save a public bookmark from another user to the current user's collection."""
    data = request.get_json()
    if not data or "bookmark_id" not in data:
        return jsonify({"error": "Bookmark ID is required"}), 400

    bookmark_id = data["bookmark_id"]
    conn = get_db()
    try:
        source = conn.execute(
            f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE id = ? AND is_public = 1",
            (bookmark_id,),
        ).fetchone()
        if not source:
            return jsonify({"error": "Source bookmark not found or is not public"}), 404

        source_data = row_to_dict(source)
        existing = conn.execute(
            f"SELECT {BOOKMARK_COLUMNS} FROM bookmarks WHERE user_id = ? AND url = ?",
            (g.user.id, source_data["url"]),
        ).fetchone()
        if existing:
            return jsonify({
                "message": "Bookmark already exists in your collection",
                "bookmark": _bookmark_response(existing),
                "already_exists": True,
            })

        copied_fields = [
            "url", "domain", "original_title", "clean_title", "ai_summary",
            "auto_tags", "favicon_url", "thumbnail_url", "content_type",
            "intent_type", "technical_level", "embedding",
        ]
        new_bookmark_data = {key: source_data.get(key) for key in copied_fields}
        new_bookmark_data.update({
            "user_id": g.user.id,
            "enrichment_status": "completed",
            "is_public": True,
        })
        row = _insert_bookmark(conn, new_bookmark_data)
        conn.commit()
        return jsonify(_bookmark_response(row)), 201
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to save public bookmark: {str(e)}")
        return jsonify({"error": str(e)}), 500
