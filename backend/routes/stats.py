"""Stats routes for dashboard."""
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth
from services.openai_service import AzureOpenAIService

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


@stats_bp.route("/resurface", methods=["GET"])
@require_auth
def get_resurface_suggestions():
    """Get AI-powered suggestions for old bookmarks to revisit."""
    try:
        supabase = g.supabase
        
        # Get recent bookmarks (last 2 weeks)
        two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        recent_result = supabase.table("bookmarks").select(
            "id, clean_title, ai_summary, auto_tags"
        ).eq("user_id", g.user.id).eq("enrichment_status", "completed").gte(
            "created_at", two_weeks_ago
        ).order("created_at", desc=True).limit(10).execute()
        
        recent_bookmarks = recent_result.data
        
        if len(recent_bookmarks) < 2:
            return jsonify({
                "message": "Not enough recent bookmarks for suggestions",
                "suggestions": []
            })
        
        # Get old bookmarks (older than 30 days, not accessed recently)
        month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        old_result = supabase.table("bookmarks").select(
            "id, clean_title, ai_summary, auto_tags, created_at, last_accessed_at"
        ).eq("user_id", g.user.id).eq("enrichment_status", "completed").lt(
            "created_at", month_ago
        ).order("created_at", desc=True).limit(50).execute()
        
        old_bookmarks = old_result.data
        
        if len(old_bookmarks) < 3:
            return jsonify({
                "message": "Not enough old bookmarks for suggestions",
                "suggestions": []
            })
        
        # Get AI suggestions
        suggestions = AzureOpenAIService.generate_resurface_suggestions(
            recent_bookmarks, old_bookmarks
        )
        
        # Fetch full bookmark data for suggestions
        suggestion_ids = [s["bookmark_id"] for s in suggestions if "bookmark_id" in s]
        
        if suggestion_ids:
            bookmarks_result = supabase.table("bookmarks").select(
                "id, url, domain, clean_title, ai_summary, auto_tags, "
                "favicon_url, thumbnail_url, content_type, created_at, last_accessed_at"
            ).in_("id", suggestion_ids).execute()
            
            # Map reasons to bookmarks
            reason_map = {s["bookmark_id"]: s.get("reason") for s in suggestions}
            
            result_bookmarks = []
            for bookmark in bookmarks_result.data:
                bookmark["resurface_reason"] = reason_map.get(bookmark["id"], "Related to your recent bookmarks")
                result_bookmarks.append(bookmark)
            
            return jsonify({"suggestions": result_bookmarks})
        
        return jsonify({"suggestions": []})
        
    except Exception as e:
        return jsonify({"error": f"Failed to get resurface suggestions: {str(e)}"}), 500
