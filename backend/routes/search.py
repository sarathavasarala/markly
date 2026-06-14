"""Search routes."""
from __future__ import annotations

import math

from flask import Blueprint, g, jsonify, request

from config import Config
from database import get_db, row_to_dict
from middleware.auth import require_auth
from services.openai_service import AzureOpenAIService

search_bp = Blueprint("search", __name__)


BOOKMARK_SELECT = (
    "b.id, b.user_id, b.url, b.domain, b.original_title, b.clean_title, b.ai_summary, "
    "b.auto_tags, b.favicon_url, b.thumbnail_url, b.content_type, b.intent_type, "
    "b.technical_level, b.created_at, b.updated_at, b.last_accessed_at, b.access_count, "
    "b.enrichment_status, b.is_public, b.folder_id"
)


@search_bp.route("", methods=["GET"])
@require_auth
def search_bookmarks():
    """Search bookmarks using SQLite FTS by default, semantic behind a flag."""
    query = request.args.get("q", "").strip()
    mode = request.args.get("mode", "keyword")
    limit = min(request.args.get("limit", 20, type=int), 100)
    offset = request.args.get("offset", 0, type=int)
    domain = request.args.get("domain")
    content_type = request.args.get("content_type")
    tag = request.args.get("tag")

    if not query and not tag:
        return jsonify({"error": "Search query is required"}), 400

    try:
        if mode == "semantic" and Config.ENABLE_SEMANTIC_SEARCH:
            results = _semantic_search(query, limit, domain, content_type, tag)
        else:
            mode = "keyword"
            results = _keyword_search(query, limit, offset, domain, content_type, tag)

        return jsonify({"query": query, "mode": mode, "results": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


def _keyword_search(query: str, limit: int, offset: int, domain: str = None,
                    content_type: str = None, tag: str = None) -> list:
    clauses = ["b.user_id = ?", "b.enrichment_status = 'completed'"]
    params = [g.user.id]
    if domain:
        clauses.append("b.domain = ?")
        params.append(domain)
    if content_type:
        clauses.append("b.content_type = ?")
        params.append(content_type)
    if tag:
        clauses.append("b.auto_tags LIKE ?")
        params.append(f"%{tag}%")

    conn = get_db()
    if query:
        rows = conn.execute(
            f"""
            SELECT {BOOKMARK_SELECT}
            FROM bookmarks_fts f
            JOIN bookmarks b ON b.id = f.bookmark_id
            WHERE f.bookmarks_fts MATCH ?
              AND {' AND '.join(clauses)}
            ORDER BY rank
            LIMIT ? OFFSET ?
            """,
            [query] + params + [limit, offset],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT {BOOKMARK_SELECT}
            FROM bookmarks b
            WHERE {' AND '.join(clauses)}
            ORDER BY b.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    return [row_to_dict(row) for row in rows]


def _semantic_search(query: str, limit: int, domain: str = None,
                     content_type: str = None, tag: str = None) -> list:
    query_embedding = AzureOpenAIService.generate_embedding(query)
    clauses = ["user_id = ?", "embedding IS NOT NULL", "enrichment_status = 'completed'"]
    params = [g.user.id]
    if domain:
        clauses.append("domain = ?")
        params.append(domain)
    if content_type:
        clauses.append("content_type = ?")
        params.append(content_type)
    if tag:
        clauses.append("auto_tags LIKE ?")
        params.append(f"%{tag}%")

    rows = get_db().execute(
        f"SELECT * FROM bookmarks WHERE {' AND '.join(clauses)}",
        params,
    ).fetchall()
    scored = []
    for row in rows:
        bookmark = row_to_dict(row)
        embedding = bookmark.get("embedding") or []
        if not embedding:
            continue
        similarity = _cosine_similarity(query_embedding, embedding)
        if similarity > 0.3:
            bookmark["similarity"] = round(similarity, 3)
            scored.append(bookmark)
    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:limit]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0
    return dot / (norm_a * norm_b)
