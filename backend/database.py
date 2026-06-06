"""SQLite database helpers owned by the Flask backend."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from flask import g

from config import Config


JSON_FIELDS = {"auto_tags", "key_quotes", "embedding"}


def utc_now() -> str:
    """Return a stable UTC timestamp string for SQLite rows."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Generate an application UUID."""
    return str(uuid.uuid4())


def get_db_path() -> str:
    """Return the configured SQLite database path."""
    return Config.MARKLY_DB_PATH


def _connect() -> sqlite3.Connection:
    db_path = Path(get_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    # Azure App Service persists /home on network-backed storage where WAL can
    # hang during startup. DELETE is safer for this small single-instance app.
    conn.execute(f"PRAGMA journal_mode = {Config.SQLITE_JOURNAL_MODE}")
    # Performance PRAGMAs — improve read throughput
    conn.execute("PRAGMA cache_size = -8000")       # 8 MB page cache (default ~2 MB)
    conn.execute("PRAGMA temp_store = MEMORY")       # Keep temp tables in RAM
    conn.execute("PRAGMA mmap_size = 268435456")     # Memory-map up to 256 MB of DB
    return conn


def get_db() -> sqlite3.Connection:
    """Get a request-scoped SQLite connection."""
    if "db" not in g:
        g.db = _connect()
    return g.db


@contextmanager
def db_session():
    """Open a standalone SQLite connection for background tasks."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_db(_error: Exception | None = None):
    """Close the request-scoped connection."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def initialize_database():
    """Create or migrate the SQLite schema."""
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT,
                avatar_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS folders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                icon TEXT,
                color TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS bookmarks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                domain TEXT,
                original_title TEXT,
                favicon_url TEXT,
                thumbnail_url TEXT,
                raw_notes TEXT,
                user_description TEXT,
                clean_title TEXT,
                ai_summary TEXT,
                content_extract TEXT,
                key_quotes TEXT,
                auto_tags TEXT,
                intent_type TEXT,
                technical_level TEXT,
                content_type TEXT,
                embedding TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_accessed_at TEXT,
                access_count INTEGER NOT NULL DEFAULT 0,
                enrichment_status TEXT NOT NULL DEFAULT 'pending',
                enrichment_error TEXT,
                is_public INTEGER NOT NULL DEFAULT 1,
                folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
                suggested_folder_name TEXT,
                archive_content TEXT,
                archive_format TEXT,
                archive_status TEXT NOT NULL DEFAULT 'pending',
                archive_error TEXT,
                archived_at TEXT,
                archive_word_count INTEGER,
                archive_char_count INTEGER,
                UNIQUE(user_id, url)
            );

            CREATE TABLE IF NOT EXISTS search_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                query TEXT NOT NULL,
                results_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscribers (
                id TEXT PRIMARY KEY,
                curator_username TEXT NOT NULL,
                email TEXT NOT NULL,
                subscribed_at TEXT NOT NULL,
                unsubscribed_at TEXT,
                UNIQUE(curator_username, email)
            );

            CREATE TABLE IF NOT EXISTS feeds (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                feed_url TEXT NOT NULL,
                title TEXT,
                site_url TEXT,
                favicon_url TEXT,
                etag TEXT,
                last_modified TEXT,
                last_fetched_at TEXT,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                retention_limit INTEGER NOT NULL DEFAULT 100,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, feed_url)
            );

            CREATE TABLE IF NOT EXISTS feed_items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                guid TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                published_at TEXT,
                summary TEXT,
                content TEXT,
                content_format TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                bookmark_id TEXT REFERENCES bookmarks(id) ON DELETE SET NULL,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(feed_id, guid),
                UNIQUE(user_id, url)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts USING fts5(
                bookmark_id UNINDEXED,
                user_id UNINDEXED,
                body
            );

            CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON bookmarks(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_folder_id ON bookmarks(folder_id);
            CREATE INDEX IF NOT EXISTS idx_bookmarks_public ON bookmarks(user_id, is_public);
            CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders(user_id);
            CREATE INDEX IF NOT EXISTS idx_search_history_created ON search_history(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_subscribers_curator ON subscribers(curator_username);
            CREATE INDEX IF NOT EXISTS idx_feeds_user_id ON feeds(user_id);
            CREATE INDEX IF NOT EXISTS idx_feeds_active_fetch ON feeds(is_active, last_fetched_at);
            CREATE INDEX IF NOT EXISTS idx_feed_items_inbox ON feed_items(user_id, status, published_at DESC);
            CREATE INDEX IF NOT EXISTS idx_feed_items_feed ON feed_items(feed_id, published_at DESC);
            """
        )

        # Lightweight migration to add archive columns if missing
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(bookmarks)")
        columns = [row["name"] for row in cursor.fetchall()]

        new_cols = [
            ("archive_content", "TEXT"),
            ("archive_format", "TEXT"),
            ("archive_status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("archive_error", "TEXT"),
            ("archived_at", "TEXT"),
            ("archive_word_count", "INTEGER"),
            ("archive_char_count", "INTEGER"),
        ]

        migrated = False
        for col_name, col_def in new_cols:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE bookmarks ADD COLUMN {col_name} {col_def}")
                migrated = True

        if migrated or "archive_content" in columns:
            # Backfill from content_extract to archive_content for old DBs that may have content
            rows = cursor.execute(
                """
                SELECT id, content_extract
                FROM bookmarks
                WHERE content_extract IS NOT NULL AND length(trim(content_extract)) > 0
                  AND (archive_content IS NULL OR length(trim(archive_content)) = 0)
                """
            ).fetchall()

            for row in rows:
                content = row["content_extract"]
                word_count = len(content.split())
                char_count = len(content)
                cursor.execute(
                    """
                    UPDATE bookmarks
                    SET archive_content = ?,
                        archive_format = ?,
                        archive_status = ?,
                        archive_word_count = ?,
                        archive_char_count = ?,
                        archived_at = ?
                    WHERE id = ?
                    """,
                    (content, "text", "completed", word_count, char_count, utc_now(), row["id"]),
                )
                refresh_bookmark_fts(conn, row["id"])

        # Lightweight migration to add retention_limit to feeds if missing
        cursor.execute("PRAGMA table_info(feeds)")
        feed_columns = [row["name"] for row in cursor.fetchall()]
        if "retention_limit" not in feed_columns:
            cursor.execute("ALTER TABLE feeds ADD COLUMN retention_limit INTEGER NOT NULL DEFAULT 100")

        # Lightweight migration to add content and content_format to feed_items if missing
        cursor.execute("PRAGMA table_info(feed_items)")
        feed_item_columns = [row["name"] for row in cursor.fetchall()]
        if "content" not in feed_item_columns:
            cursor.execute("ALTER TABLE feed_items ADD COLUMN content TEXT")
        if "content_format" not in feed_item_columns:
            cursor.execute("ALTER TABLE feed_items ADD COLUMN content_format TEXT")


def serialize_value(value: Any) -> Any:
    """Serialize Python values before writing to SQLite."""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Serialize a dict before inserting/updating."""
    return {key: serialize_value(value) for key, value in record.items()}


def row_to_dict(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert a SQLite row to API JSON shape."""
    if row is None:
        return None
    data = dict(row)
    for key in JSON_FIELDS:
        if key in data:
            value = data[key]
            if value in (None, ""):
                data[key] = [] if key != "embedding" else None
            elif isinstance(value, str):
                try:
                    data[key] = json.loads(value)
                except json.JSONDecodeError:
                    data[key] = [] if key != "embedding" else None
    if "is_public" in data:
        data["is_public"] = bool(data["is_public"])
    return data


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def upsert_user(email: str, *, full_name: str | None = None, avatar_url: str | None = None) -> dict[str, Any]:
    """Create or update a local user record from an authenticated identity."""
    normalized_email = email.lower().strip()
    username = normalized_email.split("@")[0]
    now = utc_now()
    with db_session() as conn:
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (normalized_email,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE users
                SET username = ?, full_name = COALESCE(?, full_name),
                    avatar_url = COALESCE(?, avatar_url), updated_at = ?
                WHERE id = ?
                """,
                (username, full_name, avatar_url, now, existing["id"]),
            )
            user_id = existing["id"]
        else:
            user_id = new_id()
            conn.execute(
                """
                INSERT INTO users (id, email, username, full_name, avatar_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, normalized_email, username, full_name, avatar_url, now, now),
            )
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(user)


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    row = get_db().execute(
        "SELECT * FROM users WHERE lower(username) = lower(?)",
        (username.strip("@").lower(),),
    ).fetchone()
    return row_to_dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    row = get_db().execute("SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
    return row_to_dict(row)


def bookmark_search_body(bookmark: dict[str, Any]) -> str:
    tags = bookmark.get("auto_tags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except json.JSONDecodeError:
            tags = []
    return " ".join(
        str(part)
        for part in [
            bookmark.get("url"),
            bookmark.get("domain"),
            bookmark.get("original_title"),
            bookmark.get("clean_title"),
            bookmark.get("ai_summary"),
            bookmark.get("raw_notes"),
            bookmark.get("user_description"),
            bookmark.get("archive_content"),
            " ".join(tags),
        ]
        if part
    )


def refresh_bookmark_fts(conn: sqlite3.Connection, bookmark_id: str):
    bookmark = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
    conn.execute("DELETE FROM bookmarks_fts WHERE bookmark_id = ?", (bookmark_id,))
    if bookmark:
        data = row_to_dict(bookmark)
        conn.execute(
            "INSERT INTO bookmarks_fts (bookmark_id, user_id, body) VALUES (?, ?, ?)",
            (bookmark_id, data["user_id"], bookmark_search_body(data)),
        )


def allowed_emails() -> set[str]:
    raw = Config.ALLOWED_EMAILS or ""
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def is_email_allowed(email: str) -> bool:
    allowed = allowed_emails()
    return not allowed or email.lower().strip() in allowed


def reset_database_for_tests(path: str | None = None):
    """Remove the test DB and initialize a clean schema."""
    db_path = path or get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)
    wal_path = f"{db_path}-wal"
    shm_path = f"{db_path}-shm"
    for sidecar in (wal_path, shm_path):
        if os.path.exists(sidecar):
            os.remove(sidecar)
    initialize_database()
