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


TECHMEME_SUMMARY = (
    '<a href="https://blog.google/innovation-and-ai/diffusion-gemma/">'
    '<img src="http://www.techmeme.com/260610/i44.jpg" /></a>\n'
    '<p><a href="https://www.techmeme.com/260610/p44#a260610p44" title="Techmeme permalink">'
    '<img src="http://www.techmeme.com/img/pml.png" /></a> '
    '<a href="https://blog.google/">The Keyword</a>:<br />'
    '<span style="font-size: 1.3em;"><b>'
    '<a href="https://blog.google/innovation-and-ai/diffusion-gemma/">'
    'Google introduces DiffusionGemma, a 26B open model</a></b></span>'
    '&nbsp; &mdash;&nbsp; Our newest open experimental model.</p>'
)

TECHMEME_SUMMARY_NO_THUMB = (
    '<p><a href="https://www.techmeme.com/260610/p43#a260610p43" title="Techmeme permalink">'
    '<img src="http://www.techmeme.com/img/pml.png" /></a> '
    'Stephanie Palazzolo / <a href="https://www.theinformation.com/">The Information</a>:<br />'
    '<span style="font-size: 1.3em;"><b>'
    '<a href="https://www.theinformation.com/briefings/openai-public-next-year">'
    'Sources: Sam Altman told staff OpenAI expects to go public within the next year</a></b></span>'
    '&nbsp; &mdash;&nbsp; OpenAI CEO Sam Altman told staff.</p>'
)


def test_resolve_aggregator_source_url_picks_deep_article():
    from services.feeds import _resolve_aggregator_source_url

    # With thumbnail: headline (longest text) wins over source label "The Keyword".
    entry = {"link": "https://www.techmeme.com/260610/p44#a260610p44", "summary": TECHMEME_SUMMARY}
    assert (
        _resolve_aggregator_source_url(entry, entry["link"])
        == "https://blog.google/innovation-and-ai/diffusion-gemma/"
    )

    # No thumbnail: still picks the headline deep link, not the homepage label.
    entry2 = {"link": "https://www.techmeme.com/260610/p43#a260610p43", "summary": TECHMEME_SUMMARY_NO_THUMB}
    assert (
        _resolve_aggregator_source_url(entry2, entry2["link"])
        == "https://www.theinformation.com/briefings/openai-public-next-year"
    )


def test_resolve_aggregator_source_url_ignores_non_aggregator_feeds():
    from services.feeds import _resolve_aggregator_source_url

    # A normal feed entry must not be rewritten even if its summary has links.
    entry = {"link": "https://example.com/post-1", "summary": '<a href="https://other.com/x">x</a>'}
    assert _resolve_aggregator_source_url(entry, entry["link"]) is None


def test_insert_aggregator_entry_uses_source_url_and_clears_content():
    from services.feeds import _insert_entry

    user = upsert_user("agg@example.com", full_name="Agg User")
    feed_id = _insert_feed(user["id"])

    entry = {
        "id": "https://www.techmeme.com/260610/p44#a260610p44",
        "link": "https://www.techmeme.com/260610/p44#a260610p44",
        "title": "Google introduces DiffusionGemma",
        "summary": TECHMEME_SUMMARY,
    }
    with db_session() as conn:
        assert _insert_entry(conn, user["id"], feed_id, entry) is True
        row = conn.execute(
            "SELECT url, guid, content, summary FROM feed_items WHERE user_id = ?",
            (user["id"],),
        ).fetchone()

    # url points at the real article so Signal extracts it; content is left empty
    # so the extractor does not treat the short aggregator blurb as full text.
    assert row["url"] == "https://blog.google/innovation-and-ai/diffusion-gemma/"
    assert row["content"] is None
    assert row["summary"] and "DiffusionGemma" in row["summary"]
    # GUID stays tied to the feed's own entry id for stable dedup.
    assert row["guid"] == "https://www.techmeme.com/260610/p44#a260610p44"


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


def test_embed_pending_feed_items_limits_and_prunes(mocker):
    from datetime import datetime, timezone, timedelta
    from services.feeds import _embed_pending_feed_items
    user = upsert_user("embed-test@example.com")
    feed_id = _insert_feed(user["id"])

    # Mock AzureOpenAIService.generate_embedding
    mocker.patch("services.openai_service.AzureOpenAIService.generate_embedding", return_value=[0.1, 0.2, 0.3])

    # We insert 505 items. 
    # Items with index 0 to 504.
    # We will insert them with descending published_at so index 0 is newest, 504 is oldest.
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        for i in range(505):
            item_id = f"item-{i}"
            pub_at = (now - timedelta(minutes=i)).isoformat()
            # For item-503 and item-504, let's seed them with an existing embedding to test pruning/nulling out
            embedding_val = "[0.9, 0.9, 0.9]" if i >= 503 else None
            conn.execute(
                """
                INSERT INTO feed_items (
                    id, user_id, feed_id, guid, url, title, published_at, status, embedding, first_seen_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)
                """,
                (
                    item_id,
                    user["id"],
                    feed_id,
                    f"guid-{i}",
                    f"https://example.com/{i}",
                    f"Title {i}",
                    pub_at,
                    embedding_val,
                    pub_at,
                    pub_at
                )
            )

    # Let's call _embed_pending_feed_items
    _embed_pending_feed_items(user["id"])

    with db_session() as conn:
        # Check top 500 items (items 0 to 499)
        # Some of them should have the mocked embedding
        rows_top = conn.execute(
            "SELECT id, embedding FROM feed_items WHERE user_id = ? ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 500",
            (user["id"],)
        ).fetchall()

        # Verify first item has embedding
        assert rows_top[0]["embedding"] is not None

        # Check items outside top 500 (indices 500 to 504)
        rows_outside = conn.execute(
            "SELECT id, embedding FROM feed_items WHERE user_id = ? ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 10 OFFSET 500",
            (user["id"],)
        ).fetchall()

        assert len(rows_outside) == 5
        for row in rows_outside:
            # All items outside the top 500 must have embedding = NULL (either because they were never embedded, or they were pruned)
            assert row["embedding"] is None


def test_feed_backoff_and_retry_after(mocker):
    from datetime import datetime, timezone
    from services.feeds import refresh_feeds
    
    user = upsert_user("backoff-test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://example.com/backoff.xml")
    
    # 1. Mock failure first to check backoff setting
    mocker.patch("services.feeds._fetch", side_effect=Exception("Connection timed out"))
    
    with db_session() as conn:
        res = refresh_feeds(conn, user["id"])
        
    assert res["feeds_checked"] == 1
    assert res["feeds_failed"] == 1
    assert res["feeds_backoff"] == 0
    
    # Check that failure_count is 1, next_retry_at is set
    with db_session() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        assert feed["failure_count"] == 1
        assert feed["next_retry_at"] is not None
        next_retry = datetime.fromisoformat(feed["next_retry_at"])
        assert next_retry > datetime.now(timezone.utc)
        
    # Check that immediate second refresh skips the feed due to backoff
    with db_session() as conn:
        res2 = refresh_feeds(conn, user["id"])
        
    assert res2["feeds_checked"] == 0
    assert res2["feeds_backoff"] == 1
    
    # Check that force=True bypasses the backoff
    mocker.patch("services.feeds._fetch", return_value=FakeResponse())
    mocker.patch("services.feeds.feedparser.parse", return_value=ParsedFeed())
    
    with db_session() as conn:
        res3 = refresh_feeds(conn, user["id"], force=True)
        
    assert res3["feeds_checked"] == 1
    assert res3["feeds_backoff"] == 0
    
    # After success, failure_count and next_retry_at should be reset
    with db_session() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        assert feed["failure_count"] == 0
        assert feed["next_retry_at"] is None
        assert feed["last_error"] is None


def test_feed_retry_after_handling(mocker):
    from datetime import datetime, timezone, timedelta
    from services.feeds import refresh_feeds
    import requests
    
    user = upsert_user("retry-test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://example.com/retry.xml")
    
    # Helper to create requests.HTTPError
    def raise_http_error(status_code, headers):
        resp = requests.Response()
        resp.status_code = status_code
        resp.headers = headers
        exc = requests.HTTPError(response=resp)
        raise exc

    # A. 429 with numeric Retry-After (seconds)
    mocker.patch("services.feeds._fetch", side_effect=lambda *a, **k: raise_http_error(429, {"Retry-After": "300"}))
    
    with db_session() as conn:
        refresh_feeds(conn, user["id"])
        
    with db_session() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        assert feed["next_retry_at"] is not None
        next_retry = datetime.fromisoformat(feed["next_retry_at"])
        # Should be roughly now + 5 minutes
        expected_time = datetime.now(timezone.utc) + timedelta(seconds=300)
        assert abs((next_retry - expected_time).total_seconds()) < 5

    # B. 503 with HTTP date Retry-After
    future_date = datetime.now(timezone.utc) + timedelta(hours=1)
    import email.utils
    http_date_str = email.utils.format_datetime(future_date)
    
    with db_session() as conn:
        conn.execute("UPDATE feeds SET failure_count = 0, next_retry_at = NULL, last_fetched_at = NULL WHERE id = ?", (feed_id,))
        
    mocker.patch("services.feeds._fetch", side_effect=lambda *a, **k: raise_http_error(503, {"Retry-After": http_date_str}))
    
    with db_session() as conn:
        refresh_feeds(conn, user["id"])
        
    with db_session() as conn:
        feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
        assert feed["next_retry_at"] is not None
        next_retry = datetime.fromisoformat(feed["next_retry_at"])
        # Should match future_date
        assert abs((next_retry - future_date).total_seconds()) < 5


def test_feed_exponential_backoff_scaling_and_disable(mocker):
    from datetime import datetime, timezone, timedelta
    from config import Config
    from services.feeds import refresh_feeds
    
    user = upsert_user("scale-test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://example.com/scale.xml")
    
    mocker.patch("services.feeds._fetch", side_effect=Exception("Failed"))
    
    for i in range(Config.FEED_MAX_FAILURES):
        with db_session() as conn:
            res = refresh_feeds(conn, user["id"], force=True)
            assert res["feeds_failed"] == 1
            
        with db_session() as conn:
            feed = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()
            assert feed["failure_count"] == i + 1
            
            # Check backoff calculation
            next_retry = datetime.fromisoformat(feed["next_retry_at"])
            expected_delay_min = min(Config.FEED_BACKOFF_BASE_MINUTES * (2 ** (feed["failure_count"] - 1)), Config.FEED_BACKOFF_MAX_MINUTES)
            expected_time = datetime.now(timezone.utc) + timedelta(minutes=expected_delay_min)
            assert abs((next_retry - expected_time).total_seconds()) < 10
            
            if i + 1 < Config.FEED_MAX_FAILURES:
                assert feed["is_active"] == 1
            else:
                assert feed["is_active"] == 0
                assert feed["last_error"].startswith("disabled after")


def test_insert_hn_entry_clears_content():
    from services.feeds import _insert_entry, should_bypass_entry_content
    
    assert should_bypass_entry_content("https://hnrss.org/best") is True
    assert should_bypass_entry_content("https://news.ycombinator.com/rss") is True
    assert should_bypass_entry_content("https://example.com/rss") is False
    
    user = upsert_user("hn-test@example.com", full_name="HN User")
    feed_id = _insert_feed(user["id"], feed_url="https://hnrss.org/best")
    
    entry = {
        "id": "https://news.ycombinator.com/item?id=123",
        "link": "https://example.com/article",
        "title": "Some Great Article",
        "summary": "<p>Points: 100, Comments: 50</p>",
    }
    
    with db_session() as conn:
        assert _insert_entry(conn, user["id"], feed_id, entry, "https://hnrss.org/best") is True
        row = conn.execute(
            "SELECT url, content, summary FROM feed_items WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        
    assert row["url"] == "https://example.com/article"
    assert row["content"] is None  # Content is cleared because it's HackerNews feed
    assert row["summary"] == "Points: 100, Comments: 50"


def test_get_item_content_retry_and_fallback(client, mocker):
    user = upsert_user("test@example.com")
    feed_id = _insert_feed(user["id"], feed_url="https://hnrss.org/best")
    
    with db_session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO feed_items (
                id, user_id, feed_id, guid, url, title, summary, content, content_format, status, first_seen_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
            """,
            (
                "retry-item-1",
                user["id"],
                feed_id,
                "hn-guid-retry",
                "https://example.com/retry-article",
                "Retry Article Title",
                "Original summary",
                None,
                None,
                utc_now(),
                utc_now(),
            )
        )
        conn.commit()

    # Mock ContentExtractor.extract to raise an error
    from services.content_extractor import ContentExtractor
    mock_extract = mocker.patch.object(ContentExtractor, "extract", side_effect=Exception("Failed connection"))

    # Attempt 1: Expect 500 error, status updated to failed_1
    res1 = client.get("/api/feeds/items/retry-item-1/content", headers=AUTH_HEADERS)
    assert res1.status_code == 500
    assert "Failed to extract content (attempt 1/3)" in res1.json["error"]
    
    with db_session() as conn:
        row = conn.execute("SELECT content, content_format FROM feed_items WHERE id = 'retry-item-1'").fetchone()
        assert row["content"] is None
        assert row["content_format"] == "failed_1"
        
    # Attempt 2: Expect 500 error, status updated to failed_2
    res2 = client.get("/api/feeds/items/retry-item-1/content", headers=AUTH_HEADERS)
    assert res2.status_code == 500
    assert "Failed to extract content (attempt 2/3)" in res2.json["error"]
    
    with db_session() as conn:
        row = conn.execute("SELECT content, content_format FROM feed_items WHERE id = 'retry-item-1'").fetchone()
        assert row["content_format"] == "failed_2"
        
    # Attempt 3: Expect 200, permanently fails, returns fallback HTML
    res3 = client.get("/api/feeds/items/retry-item-1/content", headers=AUTH_HEADERS)
    assert res3.status_code == 200
    assert "Note: Full-text extraction failed after 3 attempts" in res3.json["content"]
    assert "Original summary" in res3.json["content"]
    assert res3.json["content_format"] == "html"
    
    with db_session() as conn:
        row = conn.execute("SELECT content, content_format FROM feed_items WHERE id = 'retry-item-1'").fetchone()
        assert "Note: Full-text extraction failed" in row["content"]
        assert row["content_format"] == "html"
        
    # Future GET requests should directly return the stored fallback immediately without calling extract again
    mock_extract.reset_mock()
    mocker.patch.object(ContentExtractor, "extract")
    res4 = client.get("/api/feeds/items/retry-item-1/content", headers=AUTH_HEADERS)
    assert res4.status_code == 200
    ContentExtractor.extract.assert_not_called()


class DummyResponse:
    def __init__(self, chunks):
        self.url = "https://example.com/feed.xml"
        self.headers = {}
        self.status_code = 200
        self._content = b""
        self.closed = False
        self.chunks = chunks
        
    def raise_for_status(self):
        pass
        
    def iter_content(self, chunk_size=1):
        for chunk in self.chunks:
            yield chunk
        
    def close(self):
        self.closed = True

    @property
    def content(self):
        return self._content


def test_fetch_streaming_truncation(mocker):
    from services.feeds import _fetch
    from config import Config

    dummy_response = DummyResponse([b"a" * 65536, b"b" * 65536])
    
    mocker.patch("services.feeds.requests.get", return_value=dummy_response)
    mocker.patch("services.feeds._reject_private_host")

    mocker.patch.object(Config, "FEED_MAX_RESPONSE_BYTES", 80000)

    res = _fetch("https://example.com/feed.xml")

    assert dummy_response.closed is True
    assert len(res.content) == 131072
    assert res.content.startswith(b"a" * 65536)


def test_fetch_no_truncation(mocker):
    from services.feeds import _fetch
    from config import Config

    dummy_response = DummyResponse([b"a" * 10000, b"b" * 10000])
    
    mocker.patch("services.feeds.requests.get", return_value=dummy_response)
    mocker.patch("services.feeds._reject_private_host")

    mocker.patch.object(Config, "FEED_MAX_RESPONSE_BYTES", 50000)

    res = _fetch("https://example.com/feed.xml")

    assert dummy_response.closed is False
    assert len(res.content) == 20000
    assert res.content == b"a" * 10000 + b"b" * 10000
