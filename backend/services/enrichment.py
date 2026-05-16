"""Bookmark enrichment service."""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from config import Config
from database import db_session, refresh_bookmark_fts, row_to_dict, serialize_value, utc_now
from services.content_extractor import ContentExtractor
from services.openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)

_executor: Optional[ThreadPoolExecutor] = None


def analyze_link(
    url: str,
    user_notes: Optional[str] = None,
    folders: Optional[list[str]] = None,
    use_nano_model: bool = True,
):
    """Extract content from a URL and perform AI analysis synchronously."""
    logger.info(f"Analyzing link: {url} (nano={use_nano_model})")

    try:
        extracted = ContentExtractor.extract(url)
        logger.debug(
            f"Extracted - Title: {extracted.get('title', 'None')}, "
            f"Favicon: {extracted.get('favicon_url')}"
        )
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

    logger.info(f"Calling Azure OpenAI ({'nano' if use_nano_model else 'default'}) for analysis of {url}...")
    enriched = AzureOpenAIService.enrich_bookmark(
        url=url,
        title=extracted.get("title") or url,
        content=extracted.get("content") or extracted.get("description"),
        user_notes=user_notes,
        folders=folders,
        use_nano_model=use_nano_model,
    )

    return extracted, enriched


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=3)
    return _executor


def enrich_bookmark_async(bookmark_id: str, *, use_nano_model: bool = False):
    """Submit bookmark enrichment to background thread."""
    get_executor().submit(_enrich_bookmark, bookmark_id, use_nano_model)


def generate_embedding_async(bookmark_id: str, bookmark: dict):
    """Generate and store an embedding without blocking the request."""
    if not Config.ENABLE_EMBEDDINGS:
        return
    get_executor().submit(_generate_embedding, bookmark_id, bookmark)


def _generate_embedding(bookmark_id: str, bookmark: dict):
    try:
        text = " ".join(filter(None, [
            bookmark.get("clean_title", ""),
            bookmark.get("ai_summary", ""),
            " ".join(bookmark.get("auto_tags") or []),
            bookmark.get("raw_notes", ""),
        ]))
        if not text.strip():
            return
        embedding = AzureOpenAIService.generate_embedding(text)
        with db_session() as conn:
            conn.execute(
                "UPDATE bookmarks SET embedding = ?, updated_at = ? WHERE id = ?",
                (serialize_value(embedding), utc_now(), bookmark_id),
            )
    except Exception as e:
        logger.warning(f"[{bookmark_id}] Embedding generation failed (non-fatal): {e}")


def _enrich_bookmark(bookmark_id: str, use_nano_model: bool = False):
    """Enrich a bookmark with extracted content and AI analysis."""
    logger.info(f"Starting enrichment for bookmark {bookmark_id}")

    try:
        with db_session() as conn:
            conn.execute(
                "UPDATE bookmarks SET enrichment_status = ?, updated_at = ? WHERE id = ?",
                ("processing", utc_now(), bookmark_id),
            )
            bookmark_row = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
            if not bookmark_row:
                raise ValueError(f"Bookmark {bookmark_id} not found")
            bookmark = row_to_dict(bookmark_row)

        url = bookmark["url"]
        user_description = bookmark.get("user_description")
        user_id = bookmark.get("user_id")

        with db_session() as conn:
            folders_rows = conn.execute("SELECT name FROM folders WHERE user_id = ?", (user_id,)).fetchall()
            folders_list = [row["name"] for row in folders_rows]

        if user_description:
            logger.info(f"[{bookmark_id}] Using user-provided description (skipping scrape)")
            extracted = {
                "title": bookmark.get("original_title"),
                "content": user_description,
                "description": user_description,
                "favicon_url": bookmark.get("favicon_url"),
                "thumbnail_url": None,
                "domain": bookmark.get("domain"),
            }
            enriched = AzureOpenAIService.enrich_bookmark(
                url=url,
                title=extracted.get("title") or bookmark.get("original_title"),
                content=extracted.get("content") or extracted.get("description"),
                user_notes=bookmark.get("raw_notes"),
                folders=folders_list,
                use_nano_model=use_nano_model,
            )
        else:
            extracted, enriched = analyze_link(
                url=url,
                user_notes=bookmark.get("raw_notes"),
                folders=folders_list,
                use_nano_model=use_nano_model,
            )

        was_scrape_successful = bool(extracted.get("content"))
        update_data = {
            "domain": extracted.get("domain") or bookmark.get("domain"),
            "original_title": extracted.get("title") or bookmark.get("original_title"),
            "favicon_url": extracted.get("favicon_url"),
            "thumbnail_url": extracted.get("thumbnail_url"),
            "content_extract": (extracted.get("content") or "")[:50000],
            "clean_title": enriched.get("clean_title"),
            "ai_summary": enriched.get("ai_summary"),
            "auto_tags": serialize_value(enriched.get("auto_tags", [])),
            "key_quotes": serialize_value(enriched.get("key_quotes", [])),
            "intent_type": enriched.get("intent_type"),
            "technical_level": enriched.get("technical_level"),
            "content_type": enriched.get("content_type"),
            "suggested_folder_name": enriched.get("suggested_folder"),
            "enrichment_status": "completed",
            "enrichment_error": None if was_scrape_successful else (
                "Scraping failed: content could not be extracted. "
                "Please review AI guessed metadata."
            ),
            "updated_at": utc_now(),
        }

        assignments = ", ".join(f"{key} = ?" for key in update_data)
        with db_session() as conn:
            conn.execute(
                f"UPDATE bookmarks SET {assignments} WHERE id = ?",
                tuple(update_data.values()) + (bookmark_id,),
            )
            refresh_bookmark_fts(conn, bookmark_id)

        enriched_bookmark = {**bookmark, **enriched}
        generate_embedding_async(bookmark_id, enriched_bookmark)
        logger.info(f"Finished enrichment for bookmark {bookmark_id}")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Failed to enrich bookmark {bookmark_id}: {error_msg}")
        logger.debug(traceback.format_exc())
        try:
            with db_session() as conn:
                conn.execute(
                    """
                    UPDATE bookmarks
                    SET enrichment_status = ?, enrichment_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("failed", error_msg[:500], utc_now(), bookmark_id),
                )
        except Exception:
            logger.exception("Failed to persist enrichment failure")


def retry_failed_enrichment(bookmark_id: str):
    """Retry enrichment for a failed bookmark."""
    with db_session() as conn:
        conn.execute(
            """
            UPDATE bookmarks
            SET enrichment_status = ?, enrichment_error = ?, updated_at = ?
            WHERE id = ?
            """,
            ("pending", None, utc_now(), bookmark_id),
        )
    enrich_bookmark_async(bookmark_id)
