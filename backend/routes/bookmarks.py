"""Bookmark routes."""
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
import validators

from database import get_supabase
from middleware.auth import require_auth
from services.enrichment import enrich_bookmark_async, retry_failed_enrichment

logger = logging.getLogger(__name__)
bookmarks_bp = Blueprint("bookmarks", __name__)


@bookmarks_bp.route("", methods=["POST"])
@require_auth
def create_bookmark():
    """Create a new bookmark."""
    data = request.get_json()
    
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400
    
    url = data["url"].strip()
    
    # Validate URL
    if not validators.url(url):
        return jsonify({"error": "Invalid URL format"}), 400
    
    # Extract domain
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
    except Exception:
        domain = None
    
    raw_notes = data.get("notes", "").strip() or None
    user_description = data.get("description", "").strip() or None
    
    try:
        supabase = get_supabase()
        
        # Check if URL already exists; if so, return the existing record instead of 409
        existing = supabase.table("bookmarks").select("*").eq("url", url).execute()
        
        if existing.data:
            bookmark = existing.data[0]
            bookmark.pop("embedding", None)
            return jsonify({
                "message": "Bookmark already exists",
                "bookmark": bookmark,
                "already_exists": True,
            })
        
        # Set initial title - background enrichment will scrape and improve it
        # This removes blocking I/O from the request path for faster response
        if user_description:
            # Use first line of user description as initial title
            first_line = user_description.split('\n')[0][:100].strip()
            original_title = first_line if first_line else url
        else:
            original_title = url
        
        # Use Google favicon service as placeholder until enrichment runs
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        
        # Create bookmark with minimal initial data - enrichment handles the rest
        bookmark_data = {
            "url": url,
            "domain": domain,
            "original_title": original_title,
            "clean_title": original_title,  # Will be improved by AI enrichment
            "favicon_url": favicon_url,
            "thumbnail_url": None,  # Will be set by enrichment
            "raw_notes": raw_notes,
            "user_description": user_description,
            "enrichment_status": "pending",
        }
        
        result = supabase.table("bookmarks").insert(bookmark_data).execute()
        
        if not result.data:
            return jsonify({"error": "Failed to create bookmark"}), 500
        
        bookmark = result.data[0]
        
        # Trigger background enrichment
        enrich_bookmark_async(bookmark["id"])
        
        return jsonify(bookmark), 201
        
    except Exception as e:
        return jsonify({"error": f"Failed to create bookmark: {str(e)}"}), 500


@bookmarks_bp.route("", methods=["GET"])
@require_auth
def list_bookmarks():
    """List bookmarks with optional filtering and pagination."""
    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)  # Max 100 per page
    offset = (page - 1) * per_page
    
    # Filters
    domain = request.args.get("domain")
    content_type = request.args.get("content_type")
    intent_type = request.args.get("intent_type")
    tag = request.args.get("tag")
    status = request.args.get("status")  # enrichment status
    
    # Sort
    sort_by = request.args.get("sort", "created_at")
    sort_order = request.args.get("order", "desc")
    
    try:
        supabase = get_supabase()
        
        # Build query
        query = supabase.table("bookmarks").select(
            "id, url, domain, original_title, clean_title, ai_summary, "
            "auto_tags, favicon_url, thumbnail_url, content_type, intent_type, "
            "technical_level, created_at, updated_at, last_accessed_at, "
            "access_count, enrichment_status, raw_notes",
            count="exact"
        )
        
        # Apply filters
        if domain:
            query = query.eq("domain", domain)
        if content_type:
            query = query.eq("content_type", content_type)
        if intent_type:
            query = query.eq("intent_type", intent_type)
        if tag:
            query = query.contains("auto_tags", [tag])
        if status:
            query = query.eq("enrichment_status", status)
        
        # Apply sorting
        if sort_order == "asc":
            query = query.order(sort_by, desc=False)
        else:
            query = query.order(sort_by, desc=True)
        
        # Apply pagination
        query = query.range(offset, offset + per_page - 1)
        
        result = query.execute()
        
        total = result.count or 0
        pages = (total + per_page - 1) // per_page
        
        return jsonify({
            "bookmarks": result.data,
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
    """Delete a bookmark."""
    try:
        supabase = get_supabase()
        
        result = supabase.table("bookmarks").delete().eq(
            "id", bookmark_id
        ).execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        return jsonify({"message": "Bookmark deleted successfully"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to delete bookmark: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>/access", methods=["POST"])
@require_auth
def track_access(bookmark_id: str):
    """Track bookmark access (increment counter, update last_accessed_at)."""
    try:
        supabase = get_supabase()
        
        # Get current access count
        result = supabase.table("bookmarks").select(
            "access_count"
        ).eq("id", bookmark_id).single().execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        current_count = result.data.get("access_count", 0) or 0
        
        # Update access count and timestamp
        supabase.table("bookmarks").update({
            "access_count": current_count + 1,
            "last_accessed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", bookmark_id).execute()
        
        return jsonify({"access_count": current_count + 1})
        
    except Exception as e:
        return jsonify({"error": f"Failed to track access: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>/retry", methods=["POST"])
@require_auth
def retry_enrichment(bookmark_id: str):
    """Retry failed enrichment for a bookmark."""
    try:
        supabase = get_supabase()
        
        # Check bookmark exists and is in failed state
        result = supabase.table("bookmarks").select(
            "enrichment_status"
        ).eq("id", bookmark_id).single().execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        retry_failed_enrichment(bookmark_id)
        
        return jsonify({"message": "Enrichment retry started"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to retry enrichment: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>", methods=["GET"])
@require_auth
def get_bookmark(bookmark_id: str):
    """Get a single bookmark by ID (kept for completeness)."""
    try:
        supabase = get_supabase()
        result = supabase.table("bookmarks").select("*").eq(
            "id", bookmark_id
        ).single().execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        bookmark = result.data
        bookmark.pop("embedding", None)
        return jsonify(bookmark)
    except Exception as e:
        if "PGRST116" in str(e):
            return jsonify({"error": "Bookmark not found"}), 404
        return jsonify({"error": f"Failed to get bookmark: {str(e)}"}), 500
