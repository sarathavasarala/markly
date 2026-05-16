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
        "folder_id": overrides.pop("folder_id", None),
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


def test_public_bookmarks_do_not_include_folder_id(client):
    owner = upsert_user("profileowner@example.com", full_name="Profile Owner")
    _insert_bookmark(owner["id"], folder_id=None)

    response = client.get("/api/public/@profileowner/bookmarks")

    assert response.status_code == 200
    for bookmark in response.get_json()["bookmarks"]:
        assert "folder_id" not in bookmark


def test_save_public_does_not_copy_folder(client):
    owner = upsert_user("owner@example.com", full_name="Owner")
    with db_session() as conn:
        folder_id = new_id()
        now = utc_now()
        conn.execute(
            """
            INSERT INTO folders (id, user_id, name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (folder_id, owner["id"], "Source Folder", now, now),
        )
    source_id = _insert_bookmark(owner["id"], url="https://organized.com", folder_id=folder_id)

    response = client.post("/api/bookmarks/save-public", json={"bookmark_id": source_id}, headers=AUTH_HEADERS)

    assert response.status_code == 201
    assert response.get_json().get("folder_id") is None


def test_folder_operations_require_auth(client):
    assert client.get("/api/folders").status_code == 401
    assert client.post("/api/folders", json={"name": "Test"}).status_code == 401
    assert client.delete("/api/folders/some-id").status_code == 401


def test_list_folders_only_returns_own(client):
    user = upsert_user("test@example.com", full_name="Test User")
    other = upsert_user("other@example.com", full_name="Other")
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO folders (id, user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), user["id"], "My Folder", now, now),
        )
        conn.execute(
            "INSERT INTO folders (id, user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), other["id"], "Other Folder", now, now),
        )

    response = client.get("/api/folders", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["name"] == "My Folder"


def test_public_profile_shows_is_saved_by_viewer(client):
    viewer = upsert_user("test@example.com", full_name="Viewer")
    owner = upsert_user("otheruser@example.com", full_name="Other User")
    _insert_bookmark(owner["id"], url="https://saved.com", is_public=True)
    _insert_bookmark(owner["id"], url="https://notsaved.com", is_public=True)
    _insert_bookmark(viewer["id"], url="https://saved.com", is_public=True)

    response = client.get("/api/public/@otheruser/bookmarks", headers=AUTH_HEADERS)

    assert response.status_code == 200
    bookmarks = response.get_json()["bookmarks"]
    saved = {bookmark["url"]: bookmark["is_saved_by_viewer"] for bookmark in bookmarks}
    assert saved["https://saved.com"] is True
    assert saved["https://notsaved.com"] is False


def test_owner_can_see_private_bookmarks(client):
    user = upsert_user("test@example.com", full_name="Viewer")
    _insert_bookmark(user["id"], url="https://public.com", is_public=True)
    _insert_bookmark(user["id"], url="https://private.com", is_public=False)

    response = client.get("/api/public/@test/bookmarks", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.get_json()
    assert data["is_owner"] is True
    assert len(data["bookmarks"]) == 2
