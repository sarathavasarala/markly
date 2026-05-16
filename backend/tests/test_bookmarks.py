from database import db_session, new_id, refresh_bookmark_fts, serialize_record, upsert_user, utc_now


AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}


def _insert_bookmark(user_id: str, **overrides):
    bookmark_id = overrides.pop("id", new_id())
    now = utc_now()
    data = {
        "id": bookmark_id,
        "user_id": user_id,
        "url": overrides.pop("url", "https://example.com"),
        "domain": overrides.pop("domain", "example.com"),
        "original_title": overrides.pop("original_title", "Example"),
        "clean_title": overrides.pop("clean_title", "Example"),
        "ai_summary": overrides.pop("ai_summary", "A useful example"),
        "auto_tags": overrides.pop("auto_tags", ["example"]),
        "key_quotes": overrides.pop("key_quotes", []),
        "enrichment_status": overrides.pop("enrichment_status", "completed"),
        "is_public": overrides.pop("is_public", True),
        "created_at": now,
        "updated_at": now,
        **overrides,
    }
    serialized = serialize_record(data)
    with db_session() as conn:
        conn.execute(
            f"INSERT INTO bookmarks ({', '.join(serialized)}) VALUES ({', '.join('?' for _ in serialized)})",
            tuple(serialized.values()),
        )
        refresh_bookmark_fts(conn, bookmark_id)
    return bookmark_id


def test_list_bookmarks(client):
    user = upsert_user("test@example.com", full_name="Test User")
    _insert_bookmark(user["id"], url="https://example.com")

    response = client.get("/api/bookmarks", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["bookmarks"]) == 1
    assert data["bookmarks"][0]["url"] == "https://example.com"


def test_create_bookmark_invalid_url(client):
    response = client.post("/api/bookmarks", json={"url": "not-a-url"}, headers=AUTH_HEADERS)

    assert response.status_code == 400
    assert "Invalid URL format" in response.get_json()["error"]


def test_create_bookmark_success(client, mocker):
    mocker.patch("routes.bookmarks.enrich_bookmark_async")

    response = client.post("/api/bookmarks", json={"url": "https://new.com"}, headers=AUTH_HEADERS)

    assert response.status_code == 201
    assert response.get_json()["url"] == "https://new.com"


def test_bookmark_isolation_delete(client):
    other_user = upsert_user("other@example.com", full_name="Other User")
    bookmark_id = _insert_bookmark(other_user["id"], url="https://private.example")

    response = client.delete(f"/api/bookmarks/{bookmark_id}", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_save_public_bookmark_creation(client):
    owner = upsert_user("owner@example.com", full_name="Owner")
    source_id = _insert_bookmark(owner["id"], url="https://pub.com", is_public=True)

    response = client.post(
        "/api/bookmarks/save-public",
        json={"bookmark_id": source_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["url"] == "https://pub.com"
    assert data["id"] != source_id


def test_public_profile_visibility(client):
    owner = upsert_user("profile@example.com", full_name="Profile Owner")
    _insert_bookmark(owner["id"], url="https://public-only.com", is_public=True)
    _insert_bookmark(owner["id"], url="https://hidden.com", is_public=False)

    response = client.get("/api/public/@profile/bookmarks")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["bookmarks"]) == 1
    assert data["bookmarks"][0]["url"] == "https://public-only.com"
