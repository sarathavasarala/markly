"""Background archiving service."""
from __future__ import annotations

import logging
import traceback
from typing import Optional

from database import db_session, refresh_bookmark_fts, row_to_dict, serialize_value, utc_now
from services.content_extractor import ContentExtractor
from services.enrichment import get_executor

logger = logging.getLogger(__name__)


def archive_bookmark_async(bookmark_id: str) -> None:
    """Submit bookmark archiving to background thread."""
    get_executor().submit(_archive_bookmark, bookmark_id)


def _archive_bookmark(bookmark_id: str) -> None:
    """Archiving process for a single bookmark."""
    logger.info(f"Starting archiving for bookmark {bookmark_id}")
    
    try:
        with db_session() as conn:
            conn.execute(
                "UPDATE bookmarks SET archive_status = ?, archive_error = ?, updated_at = ? WHERE id = ?",
                ("processing", None, utc_now(), bookmark_id),
            )
            bookmark_row = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
            if not bookmark_row:
                raise ValueError(f"Bookmark {bookmark_id} not found")
            bookmark = row_to_dict(bookmark_row)
            
        url = bookmark["url"]
        
        # Perform content extraction
        extracted = ContentExtractor.extract(url)
        content = extracted.get("content")
        
        if content and content.strip():
            # Calculate counts
            word_count = len(content.split())
            char_count = len(content)
            
            update_data = {
                "archive_content": content,
                "archive_format": extracted.get("content_format") or "text",
                "archive_status": "completed",
                "archive_error": None,
                "archived_at": utc_now(),
                "archive_word_count": word_count,
                "archive_char_count": char_count,
                "updated_at": utc_now(),
            }
            
            assignments = ", ".join(f"{key} = ?" for key in update_data)
            with db_session() as conn:
                conn.execute(
                    f"UPDATE bookmarks SET {assignments} WHERE id = ?",
                    tuple(update_data.values()) + (bookmark_id,),
                )
                refresh_bookmark_fts(conn, bookmark_id)
            logger.info(f"Finished archiving for bookmark {bookmark_id} (completed)")
        else:
            # No content extracted, mark as failed/unavailable
            error_msg = "Scraping failed: no content could be extracted from page."
            update_data = {
                "archive_status": "failed",
                "archive_error": error_msg,
                "updated_at": utc_now(),
            }
            assignments = ", ".join(f"{key} = ?" for key in update_data)
            with db_session() as conn:
                conn.execute(
                    f"UPDATE bookmarks SET {assignments} WHERE id = ?",
                    tuple(update_data.values()) + (bookmark_id,),
                )
            logger.warning(f"Archiving failed for bookmark {bookmark_id}: No content extracted.")
            
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Failed to archive bookmark {bookmark_id}: {error_msg}")
        logger.debug(traceback.format_exc())
        try:
            with db_session() as conn:
                conn.execute(
                    """
                    UPDATE bookmarks
                    SET archive_status = ?, archive_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("failed", error_msg[:500], utc_now(), bookmark_id),
                )
        except Exception:
            logger.exception("Failed to persist archiving failure")


def retry_archive(bookmark_id: str) -> None:
    """Reset status and queue archiving."""
    with db_session() as conn:
        conn.execute(
            """
            UPDATE bookmarks
            SET archive_status = ?, archive_error = ?, updated_at = ?
            WHERE id = ?
            """,
            ("pending", None, utc_now(), bookmark_id),
        )
    archive_bookmark_async(bookmark_id)


def backfill_archives(limit: int = 10, retry_failed: bool = False) -> dict:
    """
    Synchronously backfill archives for bookmarks lacking content.
    Returns status counts dictionary.
    """
    if retry_failed:
        query = """
            SELECT id FROM bookmarks
            WHERE archive_status IN ('pending', 'failed')
               OR archive_status IS NULL
               OR archive_content IS NULL
               OR length(trim(archive_content)) = 0
            LIMIT ?
        """
    else:
        query = """
            SELECT id FROM bookmarks
            WHERE (archive_status = 'pending' OR archive_status IS NULL)
              AND (archive_content IS NULL OR length(trim(archive_content)) = 0)
            LIMIT ?
        """
        
    with db_session() as conn:
        rows = conn.execute(query, (limit,)).fetchall()
        bookmark_ids = [row["id"] for row in rows]
        
    stats = {
        "total_processed": len(bookmark_ids),
        "completed": 0,
        "failed": 0,
    }
    
    for b_id in bookmark_ids:
        try:
            _archive_bookmark(b_id)
            # Recheck status in DB to see if it completed
            with db_session() as conn:
                updated = conn.execute("SELECT archive_status FROM bookmarks WHERE id = ?", (b_id,)).fetchone()
                if updated and updated["archive_status"] == "completed":
                    stats["completed"] += 1
                else:
                    stats["failed"] += 1
        except Exception as e:
            logger.error(f"Error backfilling bookmark {b_id}: {e}")
            stats["failed"] += 1
            
    return stats
