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
        "ai_summary": overrides.pop("ai_summary", "Summary"),
        "auto_tags": overrides.pop("auto_tags", ["tag"]),
        "key_quotes": [],
        "enrichment_status": "completed",
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


def test_save_public_bookmark_duplicate_detected(client):
    viewer = upsert_user("test@example.com", full_name="Test User")
    owner = upsert_user("owner@example.com", full_name="Owner")
    source_id = _insert_bookmark(owner["id"], url="https://duplicate.com", is_public=True)
    existing_id = _insert_bookmark(viewer["id"], url="https://duplicate.com", is_public=True)

    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": source_id}, headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.get_json()
    assert data["already_exists"] is True
    assert data["bookmark"]["id"] == existing_id


def test_save_public_bookmark_new_save_success(client):
    owner = upsert_user("owner@example.com", full_name="Owner")
    source_id = _insert_bookmark(owner["id"], url="https://newbookmark.com", is_public=True)

    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": source_id}, headers=AUTH_HEADERS)

    assert response.status_code == 201
    assert response.get_json()["url"] == "https://newbookmark.com"


def test_save_public_bookmark_not_found(client):
    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": "missing"}, headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert "not found" in response.get_json()["error"].lower()


def test_save_public_bookmark_not_public(client):
    owner = upsert_user("owner@example.com", full_name="Owner")
    source_id = _insert_bookmark(owner["id"], url="https://private.com", is_public=False)

    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": source_id}, headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_save_public_bookmark_missing_id(client):
    response = client.post("/api/bookmarks/save-public", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 400
    assert "required" in response.get_json()["error"].lower()


def test_save_public_bookmark_unauthenticated(client):
    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": "some-id"})

    assert response.status_code == 401


def test_public_profile_hides_private_bookmarks(client):
    owner = upsert_user("testuser@example.com", full_name="Test User")
    _insert_bookmark(owner["id"], url="https://public.com", is_public=True)
    _insert_bookmark(owner["id"], url="https://private.com", is_public=False)

    response = client.get("/api/public/@testuser/bookmarks")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["bookmarks"]) == 1
    assert data["bookmarks"][0]["is_public"] is True


def test_owner_sees_all_bookmarks_on_own_profile(client):
    owner = upsert_user("test@example.com", full_name="Test User")
    _insert_bookmark(owner["id"], url="https://public.com", is_public=True)
    _insert_bookmark(owner["id"], url="https://private.com", is_public=False)

    response = client.get("/api/public/@test/bookmarks", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.get_json()
    assert data["is_owner"] is True
    assert len(data["bookmarks"]) == 2
