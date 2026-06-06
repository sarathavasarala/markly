from unittest.mock import patch, MagicMock
from database import db_session, new_id, refresh_bookmark_fts, row_to_dict, initialize_database, get_db
from services.archive import _archive_bookmark, retry_archive, backfill_archives
from routes.bookmarks import BOOKMARK_COLUMNS

AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}


def _insert_test_bookmark(user_id: str, **overrides):
    bookmark_id = overrides.pop("id", new_id())
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
        "archive_status": overrides.pop("archive_status", "pending"),
        "is_public": overrides.pop("is_public", True),
        "created_at": "2026-06-06T10:00:00Z",
        "updated_at": "2026-06-06T10:00:00Z",
        **overrides,
    }
    from database import serialize_record
    serialized = serialize_record(data)
    with db_session() as conn:
        conn.execute(
            f"INSERT INTO bookmarks ({', '.join(serialized)}) VALUES ({', '.join('?' for _ in serialized)})",
            tuple(serialized.values()),
        )
        refresh_bookmark_fts(conn, bookmark_id)
    return bookmark_id


def test_archive_fields_in_db_schema(app):
    """Verify that initialize_database creates all required columns."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(bookmarks)")
        columns = [row["name"] for row in cursor.fetchall()]
        
        assert "archive_content" in columns
        assert "archive_format" in columns
        assert "archive_status" in columns
        assert "archive_error" in columns
        assert "archived_at" in columns
        assert "archive_word_count" in columns
        assert "archive_char_count" in columns


@patch("services.content_extractor.ContentExtractor.extract")
def test_archive_bookmark_success(mock_extract, app):
    """Test successful archiving task."""
    mock_extract.return_value = {
        "title": "Success Article",
        "description": "Success desc",
        "content": "This is the archived text content of the article.",
        "content_format": "text",
        "favicon_url": "https://example.com/favicon.ico",
        "thumbnail_url": None,
        "domain": "example.com",
    }
    
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(user["id"], url="https://example.com/art")
    
    _archive_bookmark(bookmark_id)
    
    with db_session() as conn:
        row = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        data = dict(row)
        assert data["archive_status"] == "completed"
        assert data["archive_content"] == "This is the archived text content of the article."
        assert data["archive_format"] == "text"
        assert data["archive_word_count"] == 9
        assert data["archive_char_count"] == 49
        assert data["archived_at"] is not None
        assert data["archive_error"] is None


@patch("services.content_extractor.ContentExtractor.extract")
def test_archive_bookmark_failure(mock_extract, app):
    """Test archiving failure when scraper returns no content."""
    mock_extract.return_value = {
        "title": "Failed",
        "content": None,
        "content_format": None,
    }
    
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(user["id"], url="https://example.com/fail")
    
    _archive_bookmark(bookmark_id)
    
    with db_session() as conn:
        row = conn.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        data = dict(row)
        assert data["archive_status"] == "failed"
        assert data["archive_content"] is None
        assert "no content could be extracted" in data["archive_error"]


def test_api_get_archive_completed(client):
    """Verify archive read endpoint returns 200 for completed status."""
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(
        user["id"],
        url="https://example.com/completed",
        archive_status="completed",
        archive_content="Full saved text here",
        archive_format="markdown",
        archive_word_count=4,
        archive_char_count=20,
    )
    
    response = client.get(f"/api/bookmarks/{bookmark_id}/archive", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["archive_status"] == "completed"
    assert data["archive_content"] == "Full saved text here"
    assert data["archive_format"] == "markdown"
    assert data["archive_word_count"] == 4
    assert data["archive_char_count"] == 20


def test_api_get_archive_pending(client):
    """Verify archive read endpoint returns 202 for pending/processing status."""
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(
        user["id"],
        url="https://example.com/pending",
        archive_status="processing",
    )
    
    response = client.get(f"/api/bookmarks/{bookmark_id}/archive", headers=AUTH_HEADERS)
    assert response.status_code == 202
    data = response.get_json()
    assert data["archive_status"] == "processing"
    assert data["archive_content"] is None


def test_api_get_archive_failed(client):
    """Verify archive read endpoint returns 409 for failed status."""
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(
        user["id"],
        url="https://example.com/failed",
        archive_status="failed",
        archive_error="Network timeout",
    )
    
    response = client.get(f"/api/bookmarks/{bookmark_id}/archive", headers=AUTH_HEADERS)
    assert response.status_code == 409
    data = response.get_json()
    assert data["archive_status"] == "failed"
    assert data["archive_error"] == "Network timeout"


def test_api_get_archive_isolation(client):
    """Verify other users cannot access the archive endpoint."""
    from database import upsert_user
    other_user = upsert_user("other@example.com")
    bookmark_id = _insert_test_bookmark(
        other_user["id"],
        url="https://other.com/private",
        archive_status="completed",
        archive_content="Secret text",
    )
    
    response = client.get(f"/api/bookmarks/{bookmark_id}/archive", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_api_archive_retry(client):
    """Verify retry endpoint resets status and triggers job."""
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(
        user["id"],
        url="https://example.com/retry-test",
        archive_status="failed",
        archive_error="Error text",
    )
    
    with patch("services.archive.archive_bookmark_async") as mock_async:
        response = client.post(f"/api/bookmarks/{bookmark_id}/archive/retry", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.get_json()["message"] == "Archive retry started"
        mock_async.assert_called_once_with(bookmark_id)
        
    with db_session() as conn:
        row = conn.execute("SELECT archive_status, archive_error FROM bookmarks WHERE id = ?", (bookmark_id,)).fetchone()
        assert row["archive_status"] == "pending"
        assert row["archive_error"] is None


def test_fts_search_includes_archive_content(app):
    """Verify archived content is indexable and searchable via FTS query."""
    from database import upsert_user
    user = upsert_user("test@example.com")
    bookmark_id = _insert_test_bookmark(
        user["id"],
        url="https://fts-test.com",
        archive_status="completed",
        archive_content="Specialkeywordthatisuniqueinarchives",
    )
    
    with db_session() as conn:
        results = conn.execute(
            """
            SELECT bookmark_id FROM bookmarks_fts
            WHERE body MATCH 'Specialkeywordthatisuniqueinarchives'
            """
        ).fetchall()
        assert len(results) == 1
        assert results[0]["bookmark_id"] == bookmark_id
