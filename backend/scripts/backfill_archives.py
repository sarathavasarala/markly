#!/usr/bin/env python
"""CLI script to backfill archives for existing bookmarks."""
import argparse
import os
import sys
import time

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_session, row_to_dict
from services.archive import _archive_bookmark


def print_aggregate_stats():
    with db_session() as conn:
        total = conn.execute("SELECT COUNT(*) AS count FROM bookmarks").fetchone()["count"]
        completed = conn.execute("SELECT COUNT(*) AS count FROM bookmarks WHERE archive_status = 'completed'").fetchone()["count"]
        pending = conn.execute("SELECT COUNT(*) AS count FROM bookmarks WHERE archive_status = 'pending'").fetchone()["count"]
        failed = conn.execute("SELECT COUNT(*) AS count FROM bookmarks WHERE archive_status = 'failed'").fetchone()["count"]
        unavailable = conn.execute("SELECT COUNT(*) AS count FROM bookmarks WHERE archive_status = 'unavailable'").fetchone()["count"]
        
        # Missing content matches the recommended backfill selection query
        missing = conn.execute(
            """
            SELECT COUNT(*) AS count FROM bookmarks
            WHERE archive_status IN ('pending', 'failed')
               OR archive_status IS NULL
               OR archive_content IS NULL
               OR length(trim(archive_content)) = 0
            """
        ).fetchone()["count"]
        
        print("Aggregate Archive Counts:")
        print(f"  Total bookmarks:           {total}")
        print(f"  Completed archives:        {completed}")
        print(f"  Pending archives:          {pending}")
        print(f"  Failed archives:           {failed}")
        print(f"  Unavailable archives:      {unavailable}")
        print(f"  Remaining missing content: {missing}")


def main():
    parser = argparse.ArgumentParser(description="Backfill archives for existing bookmarks.")
    parser.add_argument("--limit", type=int, default=10, help="Batch limit (default: 10)")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed archives as well")
    parser.add_argument("--dry-run", action="store_true", help="Print stats and target bookmarks without archiving")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between bookmarks (default: 0)")
    
    args = parser.parse_args()
    
    # Query targets
    if args.retry_failed:
        query = """
            SELECT id, url, domain FROM bookmarks
            WHERE archive_status IN ('pending', 'failed')
               OR archive_status IS NULL
               OR archive_content IS NULL
               OR length(trim(archive_content)) = 0
            LIMIT ?
        """
    else:
        query = """
            SELECT id, url, domain FROM bookmarks
            WHERE (archive_status = 'pending' OR archive_status IS NULL)
              AND (archive_content IS NULL OR length(trim(archive_content)) = 0)
            LIMIT ?
        """
        
    with db_session() as conn:
        rows = conn.execute(query, (args.limit,)).fetchall()
        targets = [{"id": r["id"], "url": r["url"], "domain": r["domain"]} for r in rows]
        
    if args.dry_run:
        print("Running in DRY-RUN mode. No archiving will be executed.")
        print_aggregate_stats()
        print(f"\nBookmarks to be processed (limit {args.limit}):")
        if not targets:
            print("  No bookmarks match the selection criteria.")
        for t in targets:
            print(f"  ID: {t['id']} | Domain: {t['domain']} | URL: {t['url']}")
        return

    print("Before backfill:")
    print_aggregate_stats()
    print()
    
    if not targets:
        print("No bookmarks need backfilling.")
        return
        
    print(f"Processing {len(targets)} bookmarks...")
    succeeded_count = 0
    failed_count = 0
    
    for idx, t in enumerate(targets):
        b_id = t["id"]
        domain = t["domain"] or "unknown"
        url = t["url"]
        
        if idx > 0 and args.delay > 0:
            time.sleep(args.delay)
            
        try:
            _archive_bookmark(b_id)
            # Fetch updated status
            with db_session() as conn:
                updated = conn.execute("SELECT archive_status, archive_error FROM bookmarks WHERE id = ?", (b_id,)).fetchone()
                status = updated["archive_status"] if updated else "failed"
                
            if status == "completed":
                print(f"  [SUCCESS] ID: {b_id} | Domain: {domain}")
                succeeded_count += 1
            else:
                err = updated["archive_error"] if updated else "unknown error"
                print(f"  [FAILED]  ID: {b_id} | Domain: {domain} | Error: {err}")
                failed_count += 1
        except Exception as e:
            print(f"  [FAILED]  ID: {b_id} | Domain: {domain} | Error: {str(e)}")
            failed_count += 1
            
    print("\nBackfill Run Summary:")
    print(f"  Processed: {len(targets)}")
    print(f"  Succeeded: {succeeded_count}")
    print(f"  Failed:    {failed_count}")
    print()
    
    print("After backfill:")
    print_aggregate_stats()


if __name__ == "__main__":
    main()
