"""Bookmark routes."""
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify, g
import validators

from middleware.auth import require_auth
from services.enrichment import enrich_bookmark_async, retry_failed_enrichment, analyze_link

logger = logging.getLogger(__name__)
bookmarks_bp = Blueprint("bookmarks", __name__)


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
        
        # Merge the two into a preview object
        preview = {
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
        }
        
        return jsonify(preview)
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
    
    # Check if pre-enriched data is provided (from the Curator flow)
    is_pre_enriched = all(k in data for k in ["clean_title", "ai_summary", "auto_tags"])
    
    try:
        supabase = g.supabase
        
        # Check if URL already exists
        existing = supabase.table("bookmarks").select("*").eq("url", url).execute()
        
        if existing.data:
            bookmark = existing.data[0]
            bookmark.pop("embedding", None)
            return jsonify({
                "message": "Bookmark already exists",
                "bookmark": bookmark,
                "already_exists": True,
            })
        
        if is_pre_enriched:
            # Save data directly as provided by user/curator
            bookmark_data = {
                "url": url,
                "domain": data.get("domain") or data.get("url"),
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
            }
        else:
            # Set initial title - background enrichment will scrape and improve it
            if user_description:
                first_line = user_description.split('\n')[0][:100].strip()
                original_title = first_line if first_line else url
            else:
                original_title = url
            
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")
            except Exception:
                domain = None
                
            favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None
            
            bookmark_data = {
                "url": url,
                "domain": domain,
                "original_title": original_title,
                "clean_title": original_title,
                "favicon_url": favicon_url,
                "thumbnail_url": None,
                "raw_notes": raw_notes,
                "user_description": user_description,
                "enrichment_status": "pending",
            }
        
        result = supabase.table("bookmarks").insert(bookmark_data).execute()
        
        if not result.data:
            return jsonify({"error": "Failed to create bookmark"}), 500
        
        bookmark = result.data[0]
        
        # Trigger background enrichment only if not already done
        if not is_pre_enriched:
            enrich_bookmark_async(bookmark["id"])
        else:
            # Still trigger embedding generation in background even if pre-enriched
            from services.openai_service import AzureOpenAIService
            # We need to pass the user's token or ID context to the async task if it needs it.
            # However, embeddings are usually generated by the system.
            # BUT the update query below uses get_supabase()...
            # We should probably pass the user token to the async wrapper if possible,
            # or allow the sys admin client to update it.
            # Async tasks run outside of requets context, so they generally USE ADMIN key.
            # That is acceptable for background tasks as long as they target by ID.
            def generate_async_embedding(bid, text):
                try:
                    # Note: Async thread uses Admin Client (get_supabase)
                    # This is correct for background jobs
                    embedding = AzureOpenAIService.generate_embedding(text)
                    # We need to import get_supabase here since we removed it from top level
                    from database import get_supabase 
                    get_supabase().table("bookmarks").update({"embedding": embedding}).eq("id", bid).execute()
                except: pass
            
            emb_text = " ".join(filter(None, [
                bookmark_data["clean_title"],
                bookmark_data["ai_summary"],
                " ".join(bookmark_data["auto_tags"]),
                raw_notes
            ]))
            from concurrent.futures import ThreadPoolExecutor
            ThreadPoolExecutor().submit(generate_async_embedding, bookmark["id"], emb_text)
        
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
    tags = request.args.getlist("tag")
    status = request.args.get("status")  # enrichment status
    
    # Sort
    sort_by = request.args.get("sort", "created_at")
    sort_order = request.args.get("order", "desc")
    
    try:
        supabase = g.supabase
        
        # Build query
        query = supabase.table("bookmarks").select(
            "id, url, domain, original_title, clean_title, ai_summary, "
            "auto_tags, favicon_url, thumbnail_url, content_type, intent_type, "
            "technical_level, created_at, enrichment_status",
            count="exact"
        )
        
        # Apply filters
        if domain:
            query = query.eq("domain", domain)
        if content_type:
            query = query.eq("content_type", content_type)
        if intent_type:
            query = query.eq("intent_type", intent_type)
        if tags:
            query = query.overlaps("auto_tags", tags)
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
        supabase = g.supabase
        
        result = supabase.table("bookmarks").delete().eq(
            "id", bookmark_id
        ).execute()
        
        if not result.data:
            # If RLS filters it out, result.data is empty.
            # We can't distinguish "doesn't exist" from "not yours" easily without an extra check,
            # but usually return 404 is fine for both.
            return jsonify({"error": "Bookmark not found"}), 404
        
        return jsonify({"message": "Bookmark deleted successfully"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to delete bookmark: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>/access", methods=["POST"])
@require_auth
def track_access(bookmark_id: str):
    """Track bookmark access (increment counter, update last_accessed_at)."""
    try:
        supabase = g.supabase
        
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
        supabase = g.supabase
        
        # Check bookmark exists and is in failed state
        result = supabase.table("bookmarks").select(
            "enrichment_status"
        ).eq("id", bookmark_id).single().execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        # Pass the current user context or just trigger the background job
        # Background job uses admin access, which is fine.
        retry_failed_enrichment(bookmark_id)
        
        return jsonify({"message": "Enrichment retry started"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to retry enrichment: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>", methods=["PATCH"])
@require_auth
def update_bookmark(bookmark_id: str):
    """Update bookmark metadata."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Allowed fields for update
    allowed_fields = [
        "clean_title", "ai_summary", "auto_tags", "raw_notes", 
        "user_description", "content_type", "intent_type", "technical_level",
        "thumbnail_url"
    ]
    
    update_data = {
        k: v for k, v in data.items() if k in allowed_fields
    }
    
    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400
    
    try:
        supabase = g.supabase
        result = supabase.table("bookmarks").update(update_data).eq(
            "id", bookmark_id
        ).execute()
        
        if not result.data:
            return jsonify({"error": "Bookmark not found"}), 404
        
        return jsonify(result.data[0])
        
    except Exception as e:
        return jsonify({"error": f"Failed to update bookmark: {str(e)}"}), 500


@bookmarks_bp.route("/<bookmark_id>", methods=["GET"])
@require_auth
def get_bookmark(bookmark_id: str):
    """Get a single bookmark by ID (kept for completeness)."""
    try:
        supabase = g.supabase
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
