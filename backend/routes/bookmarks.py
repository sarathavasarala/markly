"""Bookmark routes."""
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
import validators

from database import get_supabase
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
        supabase = get_supabase()
        
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
            def generate_async_embedding(bid, text):
                try:
                    embedding = AzureOpenAIService.generate_embedding(text)
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
        "user_description", "content_type", "intent_type", "technical_level"
    ]
    
    update_data = {
        k: v for k, v in data.items() if k in allowed_fields
    }
    
    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400
    
    try:
        supabase = get_supabase()
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


@bookmarks_bp.route("/import", methods=["POST"])
@require_auth
def import_bookmarks():
    """Bulk import browser bookmarks with optional enrichment selection."""
    payload = request.get_json() or {}
    items = payload.get("bookmarks") or []
    use_nano_model = bool(payload.get("use_nano_model", True))

    if not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "bookmarks array is required"}), 400

    # Normalize and validate inputs
    normalized = []
    for raw in items:
        url = (raw.get("url") or "").strip() if isinstance(raw, dict) else ""
        if not url:
            continue
        try:
            parsed_url = url if validators.url(url) else None
        except Exception:
            parsed_url = None
        if not parsed_url:
            continue
        title = (raw.get("title") or url).strip()
        tags = raw.get("tags") or []
        tags = [str(t).strip().lower().replace(" ", "-") for t in tags if str(t).strip()]
        enrich = bool(raw.get("enrich", False))
        normalized.append({
            "url": url,
            "title": title,
            "tags": tags,
            "enrich": enrich,
        })

    if not normalized:
        return jsonify({"error": "No valid bookmarks provided"}), 400

    supabase = get_supabase()

    def chunked(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    # Create import job record
    job_result = supabase.table("import_jobs").insert({
        "status": "processing",
        "total": len(normalized),
        "use_nano_model": use_nano_model,
    }).execute()

    if not job_result.data:
        return jsonify({"error": "Failed to start import job"}), 500

    job_id = job_result.data[0]["id"]

    # Deduplicate against existing URLs
    urls = [item["url"] for item in normalized]
    existing_urls = set()
    for chunk in chunked(urls, 100):
        existing = supabase.table("bookmarks").select("url").in_("url", chunk).execute()
        existing_urls.update({row["url"] for row in (existing.data or [])})

    to_insert = []
    enrich_candidates = []
    skipped_count = 0

    for item in normalized:
        if item["url"] in existing_urls:
            skipped_count += 1
            continue

        try:
            parsed = urlparse(item["url"])
            domain = parsed.netloc.replace("www.", "")
        except Exception:
            domain = None

        enrich = item["enrich"] is True
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None

        record = {
            "url": item["url"],
            "domain": domain,
            "original_title": item["title"] or item["url"],
            "clean_title": item["title"] or item["url"],
            "favicon_url": favicon_url,
            "auto_tags": item.get("tags") or [],
            "enrichment_status": "pending" if enrich else "completed",
            "import_job_id": job_id if enrich else None,
        }

        to_insert.append(record)
        if enrich:
            enrich_candidates.append(item["url"])

    inserted: list[dict] = []
    for chunk in chunked(to_insert, 200):
        insert_result = supabase.table("bookmarks").insert(chunk).execute()
        inserted.extend(insert_result.data or [])

    # Map URLs to inserted IDs for enrichment queueing
        to_enqueue = [row for row in inserted if row.get("url") in enrich_candidates]

        # Create import_job_items rows for enrich tasks
        item_ids_by_url = {}
        if to_enqueue:
            items_payload = [
                {
                    "job_id": job_id,
                    "url": row["url"],
                    "title": row.get("clean_title") or row.get("original_title") or row["url"],
                    "tags": row.get("auto_tags") or [],
                    "bookmark_id": row["id"],
                    "status": "pending",
                }
                for row in to_enqueue
            ]
            # batch insert items
            for chunk in chunked(items_payload, 200):
                res = supabase.table("import_job_items").insert(chunk).execute()
                data_rows = res.data or []
                for payload, created in zip(chunk, data_rows):
                    item_ids_by_url[payload["url"]] = created.get("id")

        to_enqueue_ids = [row["id"] for row in to_enqueue]

    # Update import job counts
    supabase.table("import_jobs").update({
        "imported_count": len(inserted),
        "skipped_count": len(normalized) - len(inserted),
        "enqueue_enrich_count": len(to_enqueue_ids),
        "status": "processing" if to_enqueue_ids else "completed",
    }).eq("id", job_id).execute()

    # Queue enrichments
    for row in to_enqueue:
        item_id = item_ids_by_url.get(row.get("url"))
        enrich_bookmark_async(row["id"], use_nano_model=use_nano_model, import_job_id=job_id, import_item_id=item_id)

    return jsonify({
        "job_id": job_id,
        "imported": len(inserted),
        "skipped": len(normalized) - len(inserted),
        "enrichment_queued": len(to_enqueue_ids),
        "use_nano_model": use_nano_model,
    }), 202


@bookmarks_bp.route("/import/<job_id>", methods=["GET"])
@require_auth
def get_import_job(job_id: str):
    """Return import job status and counters."""
    supabase = get_supabase()
    try:
        with_items = request.args.get("with_items", "false").lower() == "true"
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        per_page = min(max(per_page, 1), 200)
        offset = (page - 1) * per_page

        result = supabase.table("import_jobs").select("*").eq("id", job_id).single().execute()
        if not result.data:
            return jsonify({"error": "Import job not found"}), 404

        job = result.data

        current_item = None
        if job.get("current_item_id"):
            current = supabase.table("import_job_items").select("*").eq("id", job["current_item_id"]).single().execute()
            current_item = current.data if current.data else None

        items = []
        total_items = 0
        if with_items:
            items_res = supabase.table("import_job_items").select("*", count="exact").eq("job_id", job_id).range(offset, offset + per_page - 1).order("created_at", desc=False).execute()
            items = items_res.data or []
            total_items = items_res.count or 0

        return jsonify({
            "job": job,
            "current_item": current_item,
            "items": items,
            "items_total": total_items,
            "page": page,
            "per_page": per_page,
        })
    except Exception as e:
        return jsonify({"error": f"Failed to fetch import job: {str(e)}"}), 500


@bookmarks_bp.route("/import/<job_id>/stop", methods=["POST"])
@require_auth
def stop_import_job(job_id: str):
    """Mark an import job as canceled; workers will honor this."""
    supabase = get_supabase()
    try:
        supabase.table("import_jobs").update({"status": "canceled", "last_error": "Manually canceled"}).eq("id", job_id).execute()
        supabase.table("import_job_items").update({"status": "canceled", "error": "Canceled"}).eq("job_id", job_id).eq("status", "pending").execute()
        return jsonify({"message": "Job canceled"})
    except Exception as e:
        return jsonify({"error": f"Failed to cancel job: {str(e)}"}), 500


@bookmarks_bp.route("/import/<job_id>", methods=["DELETE"])
@require_auth
def delete_import_job(job_id: str):
    """Delete an import job; optionally delete bookmarks created by it."""
    supabase = get_supabase()
    remove_bookmarks = request.args.get("remove_bookmarks", "false").lower() == "true"
    try:
        if remove_bookmarks:
            supabase.table("bookmarks").delete().eq("import_job_id", job_id).execute()
        supabase.table("import_jobs").delete().eq("id", job_id).execute()
        return jsonify({"message": "Job deleted"})
    except Exception as e:
        return jsonify({"error": f"Failed to delete job: {str(e)}"}), 500


@bookmarks_bp.route("/import/<job_id>/items/<item_id>/skip", methods=["POST"])
@require_auth
def skip_import_item(job_id: str, item_id: str):
    """Skip a specific import job item."""
    supabase = get_supabase()
    try:
        # Mark item skipped if pending/processing
        supabase.table("import_job_items").update({
            "status": "skipped",
            "error": "Manually skipped",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", item_id).eq("job_id", job_id).in_("status", ["pending", "processing"]).execute()

        # If this item was current, clear it
        supabase.table("import_jobs").update({"current_item_id": None}).eq("id", job_id).eq("current_item_id", item_id).execute()
        return jsonify({"message": "Item skipped"})
    except Exception as e:
        return jsonify({"error": f"Failed to skip item: {str(e)}"}), 500
