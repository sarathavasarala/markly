"""Stats routes for dashboard."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from database import get_db
from middleware.auth import require_auth

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/tags", methods=["GET"])
@require_auth
def get_top_tags():
    """Get most used tags."""
    limit = min(request.args.get("limit", 20, type=int), 100)
    folder_id = request.args.get("folder_id")

    clauses = ["user_id = ?", "auto_tags IS NOT NULL"]
    params = [g.user.id]
    if folder_id:
        if folder_id == "unfiled":
            clauses.append("folder_id IS NULL")
        else:
            clauses.append("folder_id = ?")
            params.append(folder_id)

    try:
        rows = get_db().execute(
            f"""
            SELECT j.value AS tag, COUNT(*) AS count
            FROM bookmarks, json_each(bookmarks.auto_tags) AS j
            WHERE {' AND '.join(clauses)}
            GROUP BY j.value
            ORDER BY count DESC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
        tags = [{"tag": row["tag"], "count": row["count"]} for row in rows]
        return jsonify({"tags": tags})
    except Exception as e:
        return jsonify({"error": f"Failed to get tags: {str(e)}"}), 500
