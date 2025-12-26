"""Bookmark enrichment service."""
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from database import get_supabase
from services.content_extractor import ContentExtractor
from services.openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)

# Thread pool for background enrichment
_executor: Optional[ThreadPoolExecutor] = None


def analyze_link(url: str, user_notes: Optional[str] = None, use_nano_model: bool = False):
    """
    Extract content from a URL and perform AI analysis synchronously.
    Returns a tuple of (extracted_data, enriched_data).
    """
    logger.info(f"Analyzing link: {url}")
    
    # Step 1: Scrape
    try:
        from services.content_extractor import ContentExtractor
        extracted = ContentExtractor.extract(url)
        logger.debug(f"Extracted - Title: {extracted.get('title', 'None')}, Content length: {len(extracted.get('content', '') or '')}")
    except Exception as scrape_error:
        logger.warning(f"Scraping failed: {scrape_error}. Proceeding with URL-only enrichment.")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
        except Exception:
            domain = None
            
        extracted = {
            "title": url,
            "content": None,
            "description": None,
            "favicon_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None,
            "thumbnail_url": None,
            "domain": domain,
        }
    
    # Step 2: AI Enrichment
    logger.info(f"Calling Azure OpenAI for analysis of {url}...")
    enriched = AzureOpenAIService.enrich_bookmark(
        url=url,
        title=extracted.get("title") or url,
        content=extracted.get("content") or extracted.get("description"),
        user_notes=user_notes,
        use_nano_model=use_nano_model,
    )
    
    return extracted, enriched


def get_executor() -> ThreadPoolExecutor:
    """Get or create thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=3)
    return _executor


def enrich_bookmark_async(bookmark_id: str, *, use_nano_model: bool = False, import_job_id: str | None = None, import_item_id: str | None = None):
    """Submit bookmark enrichment to background thread."""
    executor = get_executor()
    executor.submit(_enrich_bookmark, bookmark_id, use_nano_model, import_job_id, import_item_id)


def _enrich_bookmark(bookmark_id: str, use_nano_model: bool = False, import_job_id: str | None = None, import_item_id: str | None = None):
    """
    Enrich a bookmark with extracted content and AI analysis.
    
    This runs in a background thread.
    Embedding generation is deferred - only done if LLM enrichment succeeds.
    """
    logger.info(f"Starting enrichment for bookmark {bookmark_id}")
    supabase = get_supabase()
    
    try:
        # Check job cancellation before starting
        if import_job_id and _is_job_canceled(import_job_id):
            logger.info(f"[{bookmark_id}] Job {import_job_id} canceled before start")
            if import_item_id:
                _update_item_status(import_item_id, status="canceled", error="Job canceled")
            return

        # Update status to processing
        logger.debug(f"[{bookmark_id}] Setting status to 'processing'")
        supabase.table("bookmarks").update({
            "enrichment_status": "processing"
        }).eq("id", bookmark_id).execute()

        if import_item_id and import_job_id:
            _update_item_status(import_item_id, status="processing")
            supabase.table("import_jobs").update({"current_item_id": import_item_id}).eq("id", import_job_id).execute()
        
        # Fetch bookmark
        result = supabase.table("bookmarks").select("*").eq(
            "id", bookmark_id
        ).single().execute()
        
        if not result.data:
            raise ValueError(f"Bookmark {bookmark_id} not found")
        
        bookmark = result.data
        url = bookmark["url"]
        user_description = bookmark.get("user_description")
        
        # Step 1 & 2: Get content and enrich with LLM
        if user_description:
            # User provided description - skip scraping (useful for JS-heavy sites)
            logger.info(f"[{bookmark_id}] Using user-provided description (skipping scrape)")
            extracted = {
                "title": bookmark.get("original_title"),
                "content": user_description,
                "description": user_description,
                "favicon_url": bookmark.get("favicon_url"),
                "thumbnail_url": None,
                "domain": bookmark.get("domain"),
            }
            # Call AI service directly with user-provided content
            logger.info(f"[{bookmark_id}] Calling Azure OpenAI for enrichment with user description...")
            enriched = AzureOpenAIService.enrich_bookmark(
                url=url,
                title=extracted.get("title") or bookmark.get("original_title"),
                content=extracted.get("content") or extracted.get("description"),
                user_notes=bookmark.get("raw_notes"),
                use_nano_model=use_nano_model,
            )
            logger.info(f"[{bookmark_id}] AI enrichment complete - Tags: {enriched.get('auto_tags', [])}")
        else:
            # Normal flow - scrape and analyze
            # Check cancellation before expensive call
            if import_job_id and _is_job_canceled(import_job_id):
                logger.info(f"[{bookmark_id}] Job {import_job_id} canceled before LLM call")
                if import_item_id:
                    _update_item_status(import_item_id, status="canceled", error="Job canceled")
                supabase.table("bookmarks").update({"enrichment_status": "failed", "enrichment_error": "Job canceled"}).eq("id", bookmark_id).execute()
                return
            
            extracted, enriched = analyze_link(
                url=url,
                user_notes=bookmark.get("raw_notes"),
                use_nano_model=use_nano_model
            )
            logger.info(f"[{bookmark_id}] AI enrichment complete - Tags: {enriched.get('auto_tags', [])}")
        
        # Step 3: Update bookmark with enriched data (no embedding yet)
        was_scrape_successful = bool(extracted.get("content"))
        
        update_data = {
            "domain": extracted.get("domain") or bookmark.get("domain"),
            "original_title": extracted.get("title") or bookmark.get("original_title"),
            "favicon_url": extracted.get("favicon_url"),
            "thumbnail_url": extracted.get("thumbnail_url"),
            "content_extract": (extracted.get("content") or "")[:50000],
            "clean_title": enriched.get("clean_title"),
            "ai_summary": enriched.get("ai_summary"),
            "auto_tags": enriched.get("auto_tags", []),
            "key_quotes": enriched.get("key_quotes", []),
            "intent_type": enriched.get("intent_type"),
            "technical_level": enriched.get("technical_level"),
            "content_type": enriched.get("content_type"),
            "enrichment_status": "completed",
            "enrichment_error": None if was_scrape_successful else "Scraping failed: content could not be extracted. Please review AI guessed metadata.",
        }
        
        logger.debug(f"[{bookmark_id}] Updating bookmark in database (scrape success: {was_scrape_successful})...")
        supabase.table("bookmarks").update(update_data).eq("id", bookmark_id).execute()
        
        logger.info(f"[{bookmark_id}] Enrichment complete")
        
        # Step 4: Generate embedding in a separate try-catch (non-blocking)
        # This allows the bookmark to be "completed" even if embedding fails
        try:
            embedding_text = " ".join(filter(None, [
                enriched.get("clean_title", ""),
                enriched.get("ai_summary", ""),
                " ".join(enriched.get("auto_tags", [])),
                bookmark.get("raw_notes", ""),
            ]))
            
            if embedding_text.strip():
                logger.debug(f"[{bookmark_id}] Generating embedding...")
                embedding = AzureOpenAIService.generate_embedding(embedding_text)
                supabase.table("bookmarks").update({
                    "embedding": embedding
                }).eq("id", bookmark_id).execute()
                logger.debug(f"[{bookmark_id}] Embedding saved")
        except Exception as e:
            # Log but don't fail the enrichment
            logger.warning(f"[{bookmark_id}] Embedding generation failed (non-fatal): {e}")
        
        logger.info(f"Finished enrichment for bookmark {bookmark_id}")

        if import_item_id:
            _update_item_status(import_item_id, status="completed")
        if import_job_id:
            _increment_import_job(import_job_id, completed=True)
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Failed to enrich bookmark {bookmark_id}: {error_msg}")
        logger.debug(traceback.format_exc())
        
        # Update status to failed
        try:
            supabase.table("bookmarks").update({
                "enrichment_status": "failed",
                "enrichment_error": error_msg[:500],
            }).eq("id", bookmark_id).execute()
        except Exception:
            pass

        if import_item_id:
            _update_item_status(import_item_id, status="failed", error=error_msg[:200])
        if import_job_id:
            _increment_import_job(import_job_id, failed=True)


def retry_failed_enrichment(bookmark_id: str):
    """Retry enrichment for a failed bookmark."""
    supabase = get_supabase()
    
    # Reset status to pending
    supabase.table("bookmarks").update({
        "enrichment_status": "pending",
        "enrichment_error": None,
    }).eq("id", bookmark_id).execute()
    
    # Trigger enrichment
    enrich_bookmark_async(bookmark_id)


def _increment_import_job(job_id: str, *, completed: bool = False, failed: bool = False):
    """Increment import job counters for enrichment progress."""
    supabase = get_supabase()
    try:
        # Fetch current counts
        job_res = supabase.table("import_jobs").select(
            "enrich_completed, enrich_failed, enqueue_enrich_count"
        ).eq("id", job_id).single().execute()

        if not job_res.data:
            return

        current_completed = job_res.data.get("enrich_completed", 0) or 0
        current_failed = job_res.data.get("enrich_failed", 0) or 0
        enqueue_count = job_res.data.get("enqueue_enrich_count", 0) or 0

        if completed:
            current_completed += 1
        if failed:
            current_failed += 1

        new_status = "processing"
        if enqueue_count > 0 and (current_completed + current_failed) >= enqueue_count:
            new_status = "completed"

        supabase.table("import_jobs").update({
            "enrich_completed": current_completed,
            "enrich_failed": current_failed,
            "status": new_status,
        }).eq("id", job_id).execute()
    except Exception as update_error:
        logger.warning(f"[import_job:{job_id}] Failed to update enrichment counters: {update_error}")


def _update_item_status(item_id: str, *, status: str, error: str | None = None):
    supabase = get_supabase()
    try:
        supabase.table("import_job_items").update({
            "status": status,
            "error": error,
            "started_at": datetime.now(timezone.utc).isoformat() if status == "processing" else None,
            "finished_at": datetime.now(timezone.utc).isoformat() if status in ("completed", "failed", "skipped", "canceled") else None,
        }).eq("id", item_id).execute()
    except Exception as e:
        logger.warning(f"[import_item:{item_id}] Failed to update status to {status}: {e}")


def _is_job_canceled(job_id: str) -> bool:
    supabase = get_supabase()
    try:
        res = supabase.table("import_jobs").select("status").eq("id", job_id).single().execute()
        if not res.data:
            return False
        return res.data.get("status") == "canceled"
    except Exception:
        return False
