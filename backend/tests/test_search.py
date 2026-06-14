from database import db_session, new_id, refresh_bookmark_fts, serialize_record, upsert_user, utc_now


AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}


def _insert_searchable_bookmark(user_id: str):
    bookmark_id = new_id()
    now = utc_now()
    data = {
        "id": bookmark_id,
        "user_id": user_id,
        "url": "https://example.com/privacy-search",
        "domain": "example.com",
        "original_title": "Privacy Search",
        "clean_title": "Privacy Search",
        "ai_summary": "A searchable bookmark about privacy.",
        "auto_tags": ["privacy"],
        "key_quotes": [],
        "enrichment_status": "completed",
        "is_public": False,
        "created_at": now,
        "updated_at": now,
    }
    serialized = serialize_record(data)
    with db_session() as conn:
        conn.execute(
            f"INSERT INTO bookmarks ({', '.join(serialized)}) VALUES ({', '.join('?' for _ in serialized)})",
            tuple(serialized.values()),
        )
        refresh_bookmark_fts(conn, bookmark_id)


def test_search_does_not_persist_query_history(client):
    user = upsert_user("test@example.com", full_name="Test User")
    _insert_searchable_bookmark(user["id"])

    response = client.get("/api/search?q=privacy", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.get_json()["count"] == 1
    with db_session() as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'search_history'"
        ).fetchone()
    assert table is None


def test_search_history_endpoint_is_removed(client):
    response = client.get("/api/search/history", headers=AUTH_HEADERS)

    assert response.status_code == 404
