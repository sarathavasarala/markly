"""One-time Supabase-to-SQLite migration script.

Run from the backend directory after setting:
SUPABASE_URL, SUPABASE_SERVICE_KEY, and MARKLY_DB_PATH.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import initialize_database, serialize_record, utc_now  # noqa: E402
from config import Config  # noqa: E402


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _get_json(path: str, *, headers: dict[str, str] | None = None) -> Any:
    response = requests.get(
        f"{SUPABASE_URL}{path}",
        headers=headers or _headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _fetch_table(table_name: str) -> list[dict[str, Any]]:
    return _get_json(f"/rest/v1/{table_name}?select=*")


def _fetch_users() -> list[dict[str, Any]]:
    data = _get_json("/auth/v1/admin/users?per_page=1000")
    return data.get("users", data if isinstance(data, list) else [])


def _username_from_email(email: str) -> str:
    return email.split("@")[0].lower()


def _insert_users(conn, users: list[dict[str, Any]]):
    now = utc_now()
    for user in users:
        metadata = user.get("user_metadata") or {}
        email = (user.get("email") or "").lower()
        if not email:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO users (id, email, username, full_name, avatar_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                email,
                _username_from_email(email),
                metadata.get("full_name") or metadata.get("name"),
                metadata.get("avatar_url") or metadata.get("picture"),
                user.get("created_at") or now,
                user.get("updated_at") or now,
            ),
        )


def _ensure_user(conn, user_id: str):
    if conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone():
        return
    now = utc_now()
    username = f"imported_{user_id[:8]}"
    conn.execute(
        """
        INSERT INTO users (id, email, username, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, f"{username}@imported.local", username, now, now),
    )


def _insert_rows(conn, table_name: str, rows: list[dict[str, Any]]):
    allowed_columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for row in rows:
        if row.get("user_id"):
            _ensure_user(conn, row["user_id"])
        filtered = {key: value for key, value in row.items() if key in allowed_columns}
        serialized = serialize_record(filtered)
        columns = ", ".join(serialized)
        placeholders = ", ".join("?" for _ in serialized)
        conn.execute(
            f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})",
            tuple(serialized.values()),
        )


def migrate():
    initialize_database()
    from database import db_session, refresh_bookmark_fts  # noqa: E402

    users = _fetch_users()
    folders = _fetch_table("folders")
    bookmarks = _fetch_table("bookmarks")
    search_history = _fetch_table("search_history")
    subscribers = _fetch_table("subscribers")

    with db_session() as conn:
        _insert_users(conn, users)
        _insert_rows(conn, "folders", folders)
        _insert_rows(conn, "bookmarks", bookmarks)
        _insert_rows(conn, "search_history", search_history)
        _insert_rows(conn, "subscribers", subscribers)
        for bookmark in bookmarks:
            refresh_bookmark_fts(conn, bookmark["id"])

    return {
        "db_path": Config.MARKLY_DB_PATH,
        "users": len(users),
        "folders": len(folders),
        "bookmarks": len(bookmarks),
        "search_history": len(search_history),
        "subscribers": len(subscribers),
    }


def main():
    result = migrate()
    print(f"Migrated to {result['db_path']}:")
    print(f"- users: {result['users']}")
    print(f"- folders: {result['folders']}")
    print(f"- bookmarks: {result['bookmarks']}")
    print(f"- search_history: {result['search_history']}")
    print(f"- subscribers: {result['subscribers']}")


if __name__ == "__main__":
    main()
