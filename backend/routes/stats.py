"""Stats routes for dashboard."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from database import get_db, row_to_dict
from middleware.auth import require_auth

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/tags", methods=["GET"])
@require_auth
def get_top_tags():
    """Get most used tags."""
    limit = min(request.args.get("limit", 20, type=int), 100)
    folder_id = request.args.get("folder_id")

    clauses = ["user_id = ?"]
    params = [g.user.id]
    if folder_id:
        if folder_id == "unfiled":
            clauses.append("folder_id IS NULL")
        else:
            clauses.append("folder_id = ?")
            params.append(folder_id)

    try:
        rows = get_db().execute(
            f"SELECT auto_tags FROM bookmarks WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        tag_counts = {}
        for row in rows:
            bookmark = row_to_dict(row)
            for tag in bookmark.get("auto_tags") or []:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]
        return jsonify({"tags": tags})
    except Exception as e:
        return jsonify({"error": f"Failed to get tags: {str(e)}"}), 500
