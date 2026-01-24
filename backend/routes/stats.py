"""Stats routes for dashboard."""
from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/tags", methods=["GET"])
@require_auth
def get_top_tags():
    """Get most used tags."""
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 100)
    folder_id = request.args.get("folder_id")
    
    try:
        supabase = g.supabase
        
        # Build query - ENFORCE user_id isolation
        query = supabase.table("bookmarks").select("auto_tags") \
            .eq("user_id", g.user.id)
            
        if folder_id:
            if folder_id == "unfiled":
                query = query.is_("folder_id", "null")
            else:
                query = query.eq("folder_id", folder_id)
                
        result = query.execute()
        
        # Count tags
        tag_counts = {}
        for bookmark in result.data:
            tags = bookmark.get("auto_tags") or []
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Sort by count
        sorted_tags = sorted(
            tag_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        tags = [
            {"tag": tag, "count": count}
            for tag, count in sorted_tags
        ]
        
        return jsonify({"tags": tags})
        
    except Exception as e:
        return jsonify({"error": f"Failed to get tags: {str(e)}"}), 500

