"""Bookmark enrichment service."""
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from database import get_supabase
from services.content_extractor import ContentExtractor
from services.openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)

# Thread pool for background enrichment
_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create thread pool executor."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=3)
    return _executor


def enrich_bookmark_async(bookmark_id: str):
    """Submit bookmark enrichment to background thread."""
    executor = get_executor()
    executor.submit(_enrich_bookmark, bookmark_id)


def _enrich_bookmark(bookmark_id: str):
    """
    Enrich a bookmark with extracted content and AI analysis.
    
    This runs in a background thread.
    Embedding generation is deferred - only done if LLM enrichment succeeds.
    """
    logger.info(f"Starting enrichment for bookmark {bookmark_id}")
    supabase = get_supabase()
    
    try:
        # Update status to processing
        logger.debug(f"[{bookmark_id}] Setting status to 'processing'")
        supabase.table("bookmarks").update({
            "enrichment_status": "processing"
        }).eq("id", bookmark_id).execute()
        
        # Fetch bookmark
        result = supabase.table("bookmarks").select("*").eq(
            "id", bookmark_id
        ).single().execute()
        
        if not result.data:
            raise ValueError(f"Bookmark {bookmark_id} not found")
        
        bookmark = result.data
        url = bookmark["url"]
        user_description = bookmark.get("user_description")
        
        # Step 1: Get content - either from user or by scraping
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
        else:
            # Normal flow - scrape the URL with error handling
            logger.info(f"[{bookmark_id}] Extracting content from: {url}")
            try:
                extracted = ContentExtractor.extract(url)
                logger.debug(f"[{bookmark_id}] Extracted - Title: {extracted.get('title', 'None')}, Content length: {len(extracted.get('content', '') or '')}")
            except Exception as scrape_error:
                # Scraping failed - continue with minimal data for AI enrichment
                logger.warning(f"[{bookmark_id}] Scraping failed: {scrape_error}. Proceeding with URL-only enrichment.")
                extracted = {
                    "title": bookmark.get("original_title") or url,
                    "content": None,
                    "description": None,
                    "favicon_url": bookmark.get("favicon_url"),
                    "thumbnail_url": None,
                    "domain": bookmark.get("domain"),
                }
        
        # Step 2: Enrich with LLM
        logger.info(f"[{bookmark_id}] Calling Azure OpenAI for enrichment...")
        enriched = AzureOpenAIService.enrich_bookmark(
            url=url,
            title=extracted.get("title") or bookmark.get("original_title"),
            content=extracted.get("content") or extracted.get("description"),
            user_notes=bookmark.get("raw_notes"),
        )
        logger.info(f"[{bookmark_id}] AI enrichment complete - Tags: {enriched.get('auto_tags', [])}")
        
        # Step 3: Update bookmark with enriched data (no embedding yet)
        update_data = {
            "domain": extracted.get("domain") or bookmark.get("domain"),
            "original_title": extracted.get("title") or bookmark.get("original_title"),
            "favicon_url": extracted.get("favicon_url"),
            "thumbnail_url": extracted.get("thumbnail_url"),
            "content_extract": extracted.get("content", "")[:50000],  # Limit stored content
            "clean_title": enriched.get("clean_title"),
            "ai_summary": enriched.get("ai_summary"),
            "auto_tags": enriched.get("auto_tags", []),
            "key_quotes": enriched.get("key_quotes", []),
            "intent_type": enriched.get("intent_type"),
            "technical_level": enriched.get("technical_level"),
            "content_type": enriched.get("content_type"),
            "enrichment_status": "completed",
            "enrichment_error": None,
        }
        
        logger.debug(f"[{bookmark_id}] Updating bookmark in database...")
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
