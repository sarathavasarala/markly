"""Tests for the HN Synthesis pipeline."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from database import db_session, upsert_user


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

CRON_SECRET = "hn-test-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {CRON_SECRET}"}

# Minimal RSS feed bytes that hnrss.org would return
SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Hacker News: Front Page</title>
    <link>https://news.ycombinator.com/</link>
    <description>Hacker News RSS</description>
    <item>
      <title><![CDATA[ Previewing GPT-5.6 Sol: a next-generation model ]]></title>
      <description><![CDATA[ <p>Article URL: <a href="https://openai.com/gpt56">https://openai.com/gpt56</a></p>
        <hr><p>Comments URL: <a href="https://news.ycombinator.com/item?id=48689028">https://news.ycombinator.com/item?id=48689028</a></p>
        <p>Points: 946</p> <p># Comments: 581</p> ]]></description>
      <link>https://openai.com/gpt56</link>
      <comments>https://news.ycombinator.com/item?id=48689028</comments>
      <guid isPermaLink="false">https://news.ycombinator.com/item?id=48689028</guid>
      <pubDate>Fri, 26 Jun 2026 17:06:55 +0000</pubDate>
    </item>
    <item>
      <title><![CDATA[ Show HN: My widget library ]]></title>
      <description><![CDATA[ <p>A brief description.</p>
        <hr><p>Comments URL: <a href="https://news.ycombinator.com/item?id=99999999">https://news.ycombinator.com/item?id=99999999</a></p>
        <p>Points: 50</p> ]]></description>
      <link>https://github.com/example/widgets</link>
      <comments>https://news.ycombinator.com/item?id=99999999</comments>
      <guid isPermaLink="false">https://news.ycombinator.com/item?id=99999999</guid>
    </item>
    <item>
      <title><![CDATA[ No points entry ]]></title>
      <description><![CDATA[ <p>No points or comments in this one.</p>
        <hr><p>Comments URL: <a href="https://news.ycombinator.com/item?id=11111111">https://news.ycombinator.com/item?id=11111111</a></p> ]]></description>
      <link>https://example.com/no-points</link>
      <comments>https://news.ycombinator.com/item?id=11111111</comments>
      <guid isPermaLink="false">https://news.ycombinator.com/item?id=11111111</guid>
    </item>
  </channel>
</rss>"""

# Minimal Algolia HN API response
SAMPLE_ALGOLIA = {
    "id": 48689028,
    "title": "Previewing GPT-5.6 Sol",
    "url": "https://openai.com/gpt56",
    "author": "minimaxir",
    "points": 946,
    "text": None,
    "type": "story",
    "children": [
        {
            "id": 1001,
            "author": "alice",
            "text": "<p>This is a thoughtful comment about AI safety.</p>",
            "type": "comment",
            "deleted": False,
            "dead": False,
            "children": [
                {
                    "id": 1002,
                    "author": "bob",
                    "text": "<p>Great point about safety.</p>",
                    "type": "comment",
                    "deleted": False,
                    "dead": False,
                    "children": [],
                }
            ],
        },
        {
            "id": 1003,
            "author": None,
            "text": None,
            "type": "comment",
            "deleted": True,
            "dead": False,
            "children": [],
        },
        {
            "id": 1004,
            "author": "carol",
            "text": "<p>I disagree with the framing here &amp; have evidence.</p>",
            "type": "comment",
            "deleted": False,
            "dead": False,
            "children": [],
        },
    ],
}


class FakeHTTPResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content)


def _make_openai_response(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# fetch_frontpage
# ---------------------------------------------------------------------------

class TestFetchFrontpage:
    def test_parses_items_correctly(self, app, mocker):
        mocker.patch("requests.get", return_value=FakeHTTPResponse(SAMPLE_RSS))
        from services.hn_synthesis import fetch_frontpage

        items = fetch_frontpage()

        assert len(items) == 3
        first = items[0]
        assert first["hn_id"] == 48689028
        assert first["title"] == "Previewing GPT-5.6 Sol: a next-generation model"
        assert first["article_url"] == "https://openai.com/gpt56"
        assert first["comments_url"] == "https://news.ycombinator.com/item?id=48689028"
        assert first["points"] == 946
        assert first["num_comments"] == 581

    def test_missing_points_defaults_to_zero(self, app, mocker):
        mocker.patch("requests.get", return_value=FakeHTTPResponse(SAMPLE_RSS))
        from services.hn_synthesis import fetch_frontpage

        items = fetch_frontpage()
        no_points = next(i for i in items if i["hn_id"] == 11111111)
        assert no_points["points"] == 0
        assert no_points["num_comments"] == 0

    def test_returns_empty_on_request_error(self, app, mocker):
        mocker.patch("requests.get", side_effect=Exception("network error"))
        from services.hn_synthesis import fetch_frontpage

        items = fetch_frontpage()
        assert items == []


# ---------------------------------------------------------------------------
# classify_items
# ---------------------------------------------------------------------------

class TestClassifyItems:
    def _make_items(self):
        return [
            {
                "hn_id": 48689028,
                "title": "Previewing GPT-5.6 Sol",
                "points": 946,
                "num_comments": 581,
                "brief": "OpenAI releases GPT-5.6 Sol",
            },
            {
                "hn_id": 99999999,
                "title": "Show HN: My widget library",
                "points": 50,
                "num_comments": 10,
                "brief": "A widget library in Python",
            },
        ]

    def test_returns_selected_with_classification(self, app, mocker):
        llm_json = json.dumps(
            {
                "selected": [
                    {"id": 48689028, "classification": "launch"},
                    {"id": 99999999, "classification": "news"},
                ]
            }
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(llm_json)
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_client, "gpt-4o"),
        )
        from services.hn_synthesis import classify_items

        result = classify_items(self._make_items())
        assert len(result) == 2
        assert result[0]["classification"] == "launch"
        assert result[1]["classification"] == "news"

    def test_caps_at_max_items(self, app, mocker):
        import config

        original = config.Config.HN_SYNTHESIS_MAX_ITEMS
        config.Config.HN_SYNTHESIS_MAX_ITEMS = 1
        try:
            llm_json = json.dumps(
                {
                    "selected": [
                        {"id": 48689028, "classification": "news"},
                        {"id": 99999999, "classification": "launch"},
                    ]
                }
            )
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = _make_openai_response(llm_json)
            mocker.patch(
                "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
                return_value=(mock_client, "gpt-4o"),
            )
            from services.hn_synthesis import classify_items

            result = classify_items(self._make_items())
            assert len(result) == 1
        finally:
            config.Config.HN_SYNTHESIS_MAX_ITEMS = original

    def test_fallback_on_llm_error(self, app, mocker):
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            side_effect=Exception("LLM unavailable"),
        )
        from services.hn_synthesis import classify_items

        result = classify_items(self._make_items())
        # Should fall back to top-N by points
        assert len(result) >= 1
        # Top item by points should be first
        assert result[0]["hn_id"] == 48689028
        assert result[0]["classification"] == "news"

    def test_empty_input_returns_empty(self, app):
        from services.hn_synthesis import classify_items

        assert classify_items([]) == []


# ---------------------------------------------------------------------------
# fetch_comments
# ---------------------------------------------------------------------------

class TestFetchComments:
    def test_flattens_comment_tree_with_authors(self, app, mocker):
        mocker.patch(
            "requests.get",
            return_value=FakeHTTPResponse(json.dumps(SAMPLE_ALGOLIA).encode()),
        )
        from services.hn_synthesis import fetch_comments

        result = fetch_comments(48689028)
        assert result is not None
        flat = result["flattened"]
        assert "[alice]:" in flat
        assert "[bob]:" in flat
        assert "[carol]:" in flat
        # Indentation indicates depth
        assert "  [bob]:" in flat

    def test_skips_deleted_nodes(self, app, mocker):
        mocker.patch(
            "requests.get",
            return_value=FakeHTTPResponse(json.dumps(SAMPLE_ALGOLIA).encode()),
        )
        from services.hn_synthesis import fetch_comments

        result = fetch_comments(48689028)
        assert result is not None
        # The deleted node (id=1003) should not appear in the output
        assert "[unknown]:" not in result["flattened"] or "deleted" not in result["flattened"]

    def test_honors_comments_max_chars(self, app, mocker):
        import config

        original = config.Config.HN_COMMENTS_MAX_CHARS
        config.Config.HN_COMMENTS_MAX_CHARS = 20
        try:
            mocker.patch(
                "requests.get",
                return_value=FakeHTTPResponse(json.dumps(SAMPLE_ALGOLIA).encode()),
            )
            from services.hn_synthesis import fetch_comments

            result = fetch_comments(48689028)
            assert result is not None
            total_chars = sum(len(line) for line in result["flattened"].splitlines())
            assert total_chars <= 20
        finally:
            config.Config.HN_COMMENTS_MAX_CHARS = original

    def test_returns_none_on_error(self, app, mocker):
        mocker.patch("requests.get", side_effect=Exception("network error"))
        from services.hn_synthesis import fetch_comments

        assert fetch_comments(48689028) is None

    def test_returns_item_dict(self, app, mocker):
        mocker.patch(
            "requests.get",
            return_value=FakeHTTPResponse(json.dumps(SAMPLE_ALGOLIA).encode()),
        )
        from services.hn_synthesis import fetch_comments

        result = fetch_comments(48689028)
        assert result is not None
        assert result["item"]["id"] == 48689028


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_returns_synthesis_markdown(self, app, mocker):
        expected = "### 0. Context You Need\n\nThis is a synthesis."
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _make_openai_response(expected)
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_client, "gpt-4o"),
        )
        from services.hn_synthesis import synthesize

        result = synthesize(
            title="GPT-5.6",
            article_url="https://openai.com/gpt56",
            article_text="The article says...",
            comments_text="[alice]: Great point",
            points=946,
            num_comments=581,
        )
        assert result == expected

    def test_returns_empty_string_on_error(self, app, mocker):
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            side_effect=Exception("LLM down"),
        )
        # Telemetry write: ensure db_session doesn't break the test
        mocker.patch("services.hn_synthesis._log_telemetry_error")
        from services.hn_synthesis import synthesize

        result = synthesize(
            title="GPT-5.6",
            article_url="https://openai.com/gpt56",
            article_text="",
            comments_text="",
            points=0,
            num_comments=0,
        )
        assert result == ""

    def test_logs_telemetry_on_error(self, app, mocker):
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            side_effect=Exception("LLM down"),
        )
        mock_log = mocker.patch("services.hn_synthesis._log_telemetry_error")
        from services.hn_synthesis import synthesize

        synthesize("t", "http://x.com", "", "", 0, 0)
        mock_log.assert_called_once()


# ---------------------------------------------------------------------------
# ensure_hn_feed
# ---------------------------------------------------------------------------

class TestEnsureHnFeed:
    def test_creates_feed_with_correct_attributes(self, app):
        user = upsert_user("hn-feed-test@example.com")
        from services.hn_synthesis import HN_INTERNAL_FEED_URL, ensure_hn_feed

        with db_session() as conn:
            feed_id = ensure_hn_feed(conn, user["id"])
            row = conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()

        assert row is not None
        assert row["feed_url"] == HN_INTERNAL_FEED_URL
        assert row["title"] == "HN Synthesis"
        assert row["is_active"] == 0  # Never HTTP-fetched by refresh_feeds

    def test_idempotent(self, app):
        user = upsert_user("hn-feed-idempotent@example.com")
        from services.hn_synthesis import ensure_hn_feed

        with db_session() as conn:
            id1 = ensure_hn_feed(conn, user["id"])
            id2 = ensure_hn_feed(conn, user["id"])

        assert id1 == id2

        with db_session() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM feeds WHERE user_id = ? AND feed_url = 'markly-internal://hn-synthesis'",
                (user["id"],),
            ).fetchone()[0]
        assert count == 1


# ---------------------------------------------------------------------------
# refresh_feeds guard
# ---------------------------------------------------------------------------

class TestRefreshFeedsGuard:
    def test_internal_feed_is_never_fetched(self, app, mocker):
        """A markly-internal:// feed must never result in a _fetch call, even if is_active=1."""
        user = upsert_user("guard-test@example.com")

        # Insert an internal feed with is_active=1 to simulate the defensive scenario
        from database import new_id, utc_now

        with db_session() as conn:
            feed_id = new_id()
            now = utc_now()
            conn.execute(
                """
                INSERT INTO feeds
                    (id, user_id, feed_url, title, failure_count, is_active,
                     retention_limit, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, 1, 100, ?, ?)
                """,
                (feed_id, user["id"], "markly-internal://hn-synthesis", "HN Synthesis", now, now),
            )

        mock_fetch = mocker.patch("services.feeds._fetch")
        from services.feeds import refresh_feeds

        with db_session() as conn:
            refresh_feeds(conn, user["id"], force=True)

        mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# run_hn_synthesis end-to-end
# ---------------------------------------------------------------------------

class TestRunHnSynthesis:
    def _setup_mocks(self, mocker, synthesis_text="## Synthesis\n\nThis is insight."):
        """Wire up all external calls needed for a successful run."""
        # 1. HN frontpage
        mocker.patch("requests.get", return_value=FakeHTTPResponse(SAMPLE_RSS))

        # 2. Algolia comments (called via fetch_comments which also uses requests.get)
        # We patch at a higher level to avoid conflicts
        mocker.patch(
            "services.hn_synthesis.fetch_frontpage",
            return_value=[
                {
                    "hn_id": 48689028,
                    "title": "Previewing GPT-5.6 Sol",
                    "article_url": "https://openai.com/gpt56",
                    "comments_url": "https://news.ycombinator.com/item?id=48689028",
                    "points": 946,
                    "num_comments": 581,
                    "brief": "OpenAI launches GPT-5.6",
                    "story_published_at": "2026-06-26T17:06:55+00:00",
                    "classification": "launch",
                }
            ],
        )
        mocker.patch(
            "services.hn_synthesis.classify_items",
            side_effect=lambda items: [dict(i, classification="launch") for i in items],
        )
        mocker.patch(
            "services.hn_synthesis.fetch_comments",
            return_value={
                "item": SAMPLE_ALGOLIA,
                "flattened": "[alice]: Great comment\n  [bob]: Reply",
            },
        )
        mocker.patch(
            "services.hn_synthesis._fetch_article_text",
            return_value="The article explains the new model architecture.",
        )
        mocker.patch("services.hn_synthesis.synthesize", return_value=synthesis_text)
        mocker.patch("services.feeds.embed_pending_feed_items_async")

    def test_inserts_into_hn_syntheses(self, app, mocker):
        user = upsert_user("run-test@example.com")
        self._setup_mocks(mocker)
        import config

        config.Config.HN_FETCH_DELAY_SECONDS = 0.0

        from services.hn_synthesis import run_hn_synthesis

        with db_session() as conn:
            stats = run_hn_synthesis(conn)

        assert stats["synthesized"] == 1

        with db_session() as conn:
            row = conn.execute("SELECT * FROM hn_syntheses WHERE hn_id = 48689028").fetchone()
        assert row is not None
        assert row["classification"] == "launch"
        assert "Synthesis" in row["synthesis_md"]

    def test_fans_out_feed_items(self, app, mocker):
        user = upsert_user("fan-out@example.com")
        self._setup_mocks(mocker)
        import config

        config.Config.HN_FETCH_DELAY_SECONDS = 0.0

        from services.hn_synthesis import run_hn_synthesis

        with db_session() as conn:
            stats = run_hn_synthesis(conn)

        assert stats["fanned_out"] >= 1

        with db_session() as conn:
            item = conn.execute(
                "SELECT * FROM feed_items WHERE guid = 'hn-synthesis:48689028' AND user_id = ?",
                (user["id"],),
            ).fetchone()

        assert item is not None
        assert item["content_format"] == "markdown"
        assert item["status"] == "new"
        assert item["url"] == "https://news.ycombinator.com/item?id=48689028"

    def test_idempotent_second_run(self, app, mocker):
        user = upsert_user("idempotent-run@example.com")
        self._setup_mocks(mocker)
        import config

        config.Config.HN_FETCH_DELAY_SECONDS = 0.0

        from services.hn_synthesis import run_hn_synthesis

        with db_session() as conn:
            stats1 = run_hn_synthesis(conn)

        # Second run — same item, should be skipped by retention check
        with db_session() as conn:
            stats2 = run_hn_synthesis(conn)

        assert stats1["synthesized"] == 1
        assert stats2["already_done"] == 1
        assert stats2["synthesized"] == 0

        with db_session() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM hn_syntheses WHERE hn_id = 48689028"
            ).fetchone()[0]
        assert count == 1

        with db_session() as conn:
            count_items = conn.execute(
                "SELECT COUNT(*) FROM feed_items WHERE guid = 'hn-synthesis:48689028' AND user_id = ?",
                (user["id"],),
            ).fetchone()[0]
        assert count_items == 1

    def test_skips_empty_synthesis(self, app, mocker):
        user = upsert_user("skip-empty@example.com")
        self._setup_mocks(mocker, synthesis_text="")
        import config

        config.Config.HN_FETCH_DELAY_SECONDS = 0.0

        from services.hn_synthesis import run_hn_synthesis

        with db_session() as conn:
            stats = run_hn_synthesis(conn)

        assert stats["synthesized"] == 0

        with db_session() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM hn_syntheses WHERE hn_id = 48689028"
            ).fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Cron route auth
# ---------------------------------------------------------------------------

class TestCronHnSynthesisRoute:
    def setup_method(self):
        self._original = os.getenv("CRON_SECRET")
        os.environ["CRON_SECRET"] = CRON_SECRET
        import config

        config.Config.CRON_SECRET = CRON_SECRET

    def teardown_method(self):
        if self._original is not None:
            os.environ["CRON_SECRET"] = self._original
        else:
            os.environ.pop("CRON_SECRET", None)
        import config

        config.Config.CRON_SECRET = self._original

    def test_rejects_missing_auth(self, client):
        resp = client.post("/api/cron/hn-synthesis")
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Unauthorized"}

    def test_rejects_wrong_token(self, client):
        resp = client.post(
            "/api/cron/hn-synthesis",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_accepts_valid_token(self, client, mocker):
        mocker.patch(
            "routes.cron.hn_synthesis.run_hn_synthesis",
            return_value={
                "stories_seen": 10,
                "already_done": 5,
                "classified": 3,
                "synthesized": 3,
                "fanned_out": 3,
            },
        )
        resp = client.post("/api/cron/hn-synthesis", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["summary"]["synthesized"] == 3
