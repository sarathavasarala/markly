from database import db_session, new_id, upsert_user, utc_now
from services.feeds import prune_feed_items


AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}


class ParsedFeed(dict):
    def __init__(self, *, title="Example Feed", link="https://example.com", entries=None):
        super().__init__(version="rss20")
        self.feed = {"title": title, "link": link}
        self.entries = entries or []


class FakeResponse:
    def __init__(self, url="https://example.com/feed.xml", content=b"<rss></rss>", headers=None):
        self.url = url
        self.content = content
        self.headers = headers or {"ETag": '"abc"', "Last-Modified": "Sat, 06 Jun 2026 10:00:00 GMT"}
        self.status_code = 200

    def raise_for_status(self):
        return None


def _insert_feed(user_id: str, **overrides):
    feed_id = overrides.pop("id", new_id())
    now = utc_now()
    data = {
        "id": feed_id,
        "user_id": user_id,
        "feed_url": overrides.pop("feed_url", "https://example.com/feed.xml"),
        "title": overrides.pop("title", "Example Feed"),
        "site_url": overrides.pop("site_url", "https://example.com"),
        "created_at": now,
        "updated_at": now,
        **overrides,
    }
    with db_session() as conn:
        conn.execute(
            f"INSERT INTO feeds ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
    return feed_id


def _insert_feed_item(user_id: str, feed_id: str, **overrides):
    item_id = overrides.pop("id", new_id())
    now = utc_now()
    data = {
        "id": item_id,
        "user_id": user_id,
        "feed_id": feed_id,
        "guid": overrides.pop("guid", f"guid-{item_id}"),
        "url": overrides.pop("url", f"https://example.com/{item_id}"),
        "title": overrides.pop("title", "Example item"),
        "status": overrides.pop("status", "new"),
        "first_seen_at": now,
        "updated_at": now,
        **overrides,
    }
    with db_session() as conn:
        conn.execute(
            f"INSERT INTO feed_items ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
    return item_id


def test_create_feed_discovers_and_lists(client, mocker):
    mocker.patch("services.feeds._fetch", return_value=FakeResponse())
    mocker.patch("services.feeds.feedparser.parse", return_value=ParsedFeed())

    response = client.post("/api/feeds", json={"url": "https://example.com"}, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.get_json()
    assert data["feed_url"] == "https://example.com/feed.xml"
    assert data["title"] == "Example Feed"

    list_response = client.get("/api/feeds", headers=AUTH_HEADERS)
    assert list_response.status_code == 200
    assert list_response.get_json()["feeds"][0]["new_item_count"] == 0


def test_refresh_feeds_adds_inbox_items(client, mocker):
    user = upsert_user("test@example.com")
    _insert_feed(user["id"])
    mocker.patch("services.feeds._fetch", return_value=FakeResponse())
    mocker.patch(
        "services.feeds.feedparser.parse",
        return_value=ParsedFeed(entries=[
            {
                "id": "entry-1",
                "link": "https://example.com/post-1",
                "title": "A useful post",
                "summary": "<p>A short summary</p>",
                "author": "Example Author",
            },
            {
                "id": "entry-2",
                "link": "https://example.com/post-2",
                "title": "Another post",
            },
        ]),
    )

    response = client.post("/api/feeds/refresh", json={"force": True}, headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.get_json()["items_added"] == 2

    inbox_response = client.get("/api/feeds/inbox", headers=AUTH_HEADERS)
    assert inbox_response.status_code == 200
    inbox = inbox_response.get_json()
    assert inbox["total"] == 2
    assert inbox["items"][0]["feed_title"] == "Example Feed"


def test_dismiss_feed_item_is_user_scoped(client):
    other_user = upsert_user("other@example.com")
    feed_id = _insert_feed(other_user["id"])
    item_id = _insert_feed_item(other_user["id"], feed_id)

    response = client.post(f"/api/feeds/items/{item_id}/dismiss", headers=AUTH_HEADERS)

    assert response.status_code == 404
    with db_session() as conn:
        item = conn.execute("SELECT status FROM feed_items WHERE id = ?", (item_id,)).fetchone()
        assert item["status"] == "new"


def test_mark_feed_item_saved_links_user_bookmark(client):
    user = upsert_user("test@example.com")
    feed_id = _insert_feed(user["id"])
    item_id = _insert_feed_item(user["id"], feed_id, url="https://example.com/save-me")
    bookmark_id = new_id()
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO bookmarks (
                id, user_id, url, domain, original_title, clean_title,
                auto_tags, key_quotes, enrichment_status, is_public,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bookmark_id,
                user["id"],
                "https://example.com/save-me",
                "example.com",
                "Saved",
                "Saved",
                "[]",
                "[]",
                "completed",
                1,
                now,
                now,
            ),
        )

    response = client.post(
        f"/api/feeds/items/{item_id}/saved",
        json={"bookmark_id": bookmark_id},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "saved"
    assert data["bookmark_id"] == bookmark_id


def test_prune_keeps_only_latest_n_new_or_dismissed_items():
    user = upsert_user("test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://example.com/prune1.xml", retention_limit=2)

    id1 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T12:00:00Z", status="new")
    id2 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T10:00:00Z", status="new")
    _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T08:00:00Z", status="dismissed")
    _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T06:00:00Z", status="new")

    with db_session() as conn:
        prune_feed_items(conn, user["id"], feed_id)

    with db_session() as conn:
        items = conn.execute(
            "SELECT id, status FROM feed_items WHERE feed_id = ? ORDER BY COALESCE(published_at, first_seen_at) DESC",
            (feed_id,),
        ).fetchall()
        assert len(items) == 2
        item_ids = {item["id"] for item in items}
        assert item_ids == {id1, id2}


def test_prune_preserves_saved_or_bookmarked_items():
    user = upsert_user("test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://example.com/prune2.xml", retention_limit=1)

    id1 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T12:00:00Z", status="new")
    id2 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T10:00:00Z", status="saved")
    bookmark_id = new_id()
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO bookmarks (
                id, user_id, url, domain, original_title, clean_title,
                auto_tags, key_quotes, enrichment_status, is_public,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bookmark_id,
                user["id"],
                "https://example.com/id3-bookmark",
                "example.com",
                "Saved item 3",
                "Saved item 3",
                "[]",
                "[]",
                "completed",
                1,
                now,
                now,
            ),
        )

    id3 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T08:00:00Z", status="new", bookmark_id=bookmark_id, url="https://example.com/id3-bookmark")
    id4 = _insert_feed_item(user["id"], feed_id, published_at="2026-06-06T06:00:00Z", status="new")

    with db_session() as conn:
        prune_feed_items(conn, user["id"], feed_id)

    with db_session() as conn:
        items = conn.execute("SELECT id FROM feed_items WHERE feed_id = ?", (feed_id,)).fetchall()
        item_ids = {item["id"] for item in items}
        assert id1 in item_ids
        assert id2 in item_ids
        assert id3 in item_ids
        assert id4 not in item_ids


def test_pruning_is_isolated_per_user_and_feed():
    user1 = upsert_user("user1@example.com")
    user2 = upsert_user("user2@example.com")
    
    feed1 = _insert_feed(user1["id"], retention_limit=1)
    feed2 = _insert_feed(user2["id"], retention_limit=1)
    
    u1_f1_i1 = _insert_feed_item(user1["id"], feed1, published_at="2026-06-06T12:00:00Z", status="new")
    _insert_feed_item(user1["id"], feed1, published_at="2026-06-06T10:00:00Z", status="new")
    
    _insert_feed_item(user2["id"], feed2, published_at="2026-06-06T12:00:00Z", status="new")
    _insert_feed_item(user2["id"], feed2, published_at="2026-06-06T10:00:00Z", status="new")

    with db_session() as conn:
        prune_feed_items(conn, user1["id"], feed1)

    with db_session() as conn:
        u1_items = conn.execute("SELECT id FROM feed_items WHERE feed_id = ?", (feed1,)).fetchall()
        assert len(u1_items) == 1
        assert u1_items[0]["id"] == u1_f1_i1

        u2_items = conn.execute("SELECT id FROM feed_items WHERE feed_id = ?", (feed2,)).fetchall()
        assert len(u2_items) == 2


def test_get_feed_item_content(client, mocker):
    user = upsert_user("test@example.com")
    feed_id = _insert_feed(user["id"])
    item_id = _insert_feed_item(
        user["id"],
        feed_id,
        content="<p>Saved raw RSS content</p>",
        content_format="html",
        url="https://example.com/item-1"
    )

    # 1. Test fetching cached raw content
    response = client.get(f"/api/feeds/items/{item_id}/content", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["content"] == "<p>Saved raw RSS content</p>"
    assert data["content_format"] == "html"

    # 2. Test fetching with clean extraction (mocking ContentExtractor)
    mock_extract = mocker.patch("services.content_extractor.ContentExtractor.extract", return_value={
        "content": "Clean extracted text content",
        "content_format": "markdown"
    })

    response = client.get(f"/api/feeds/items/{item_id}/content?fetch_clean=true", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["content"] == "Clean extracted text content"
    assert data["content_format"] == "markdown"
    mock_extract.assert_called_once_with("https://example.com/item-1")

    # 3. Test database is updated with extracted content
    with db_session() as conn:
        row = conn.execute("SELECT content, content_format FROM feed_items WHERE id = ?", (item_id,)).fetchone()
        assert row["content"] == "Clean extracted text content"
        assert row["content_format"] == "markdown"
