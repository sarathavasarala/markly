import os
from database import db_session, upsert_user
from tests.test_feeds import _insert_feed, _insert_feed_item


def test_cron_routes_auth(client):
    # Set the CRON_SECRET for the duration of this test
    orig_secret = os.getenv("CRON_SECRET")
    os.environ["CRON_SECRET"] = "super-secret-cron-token"

    try:
        # Test missing Authorization header
        response = client.post("/api/cron/refresh")
        assert response.status_code == 401
        assert response.get_json() == {"error": "Unauthorized"}

        response = client.post("/api/cron/brief")
        assert response.status_code == 401
        assert response.get_json() == {"error": "Unauthorized"}

        # Test incorrect Bearer token
        headers = {"Authorization": "Bearer wrong-token"}
        response = client.post("/api/cron/refresh", headers=headers)
        assert response.status_code == 401
        assert response.get_json() == {"error": "Unauthorized"}

        response = client.post("/api/cron/brief", headers=headers)
        assert response.status_code == 401
        assert response.get_json() == {"error": "Unauthorized"}
    finally:
        if orig_secret is not None:
            os.environ["CRON_SECRET"] = orig_secret
        else:
            del os.environ["CRON_SECRET"]


def test_cron_refresh_success(client, mocker):
    # Set the CRON_SECRET
    orig_secret = os.getenv("CRON_SECRET")
    os.environ["CRON_SECRET"] = "super-secret-cron-token"
    headers = {"Authorization": "Bearer super-secret-cron-token"}

    try:
        # Seed user and setup database
        user = upsert_user("cron-user@example.com", full_name="Cron User")

        # Mock refresh_feeds service function to return standard output dict
        mock_refresh_feeds = mocker.patch(
            "routes.cron.refresh_feeds",
            return_value={
                "feeds_checked": 1,
                "feeds_skipped": 0,
                "feeds_failed": 0,
                "feeds_unchanged": 0,
                "items_added": 3
            }
        )
        
        # Mock background embedding trigger
        mock_embed = mocker.patch("routes.cron.embed_pending_feed_items_async")

        # Call refresh route
        response = client.post("/api/cron/refresh", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "cron-user@example.com" in data["results"]
        assert data["results"]["cron-user@example.com"]["status"] == "success"
        assert data["results"]["cron-user@example.com"]["summary"]["items_added"] == 3

        # Check mocks were called
        mock_refresh_feeds.assert_called_once()
        mock_embed.assert_called_once_with(user["id"])
    finally:
        if orig_secret is not None:
            os.environ["CRON_SECRET"] = orig_secret
        else:
            del os.environ["CRON_SECRET"]


def test_cron_brief_success(client, mocker):
    # Set the CRON_SECRET
    orig_secret = os.getenv("CRON_SECRET")
    os.environ["CRON_SECRET"] = "super-secret-cron-token"
    headers = {"Authorization": "Bearer super-secret-cron-token"}

    try:
        # Seed user and setup database
        user = upsert_user("cron-user@example.com", full_name="Cron User")
        feed_id = _insert_feed(user["id"])
        _insert_feed_item(
            user["id"],
            feed_id,
            id="cron-item-1",
            title="Scheduled AI brief item",
            summary="Item summary",
            content="Full item text",
            content_format="html",
            status="new"
        )

        # Mock LLM and search calls
        mock_openai_client = mocker.MagicMock()
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_openai_client, "gpt-4o")
        )
        
        # Mocking filtering
        mock_response_filter = mocker.MagicMock()
        mock_response_filter.choices = [
            mocker.MagicMock(message=mocker.MagicMock(content='{"selected_ids": ["cron-item-1"]}'))
        ]
        mock_openai_client.chat.completions.create.side_effect = [mock_response_filter]
        
        # Mocking research
        mocker.patch(
            "services.openai_service.AzureOpenAIService.generate_research_with_search",
            return_value=("**Concept**: factual grounding", ["query 1"])
        )

        # Mocking synthesis
        mocker.patch(
            "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
            return_value="## Scheduled Brief Synthesis\nEverything matches the Taste Profile."
        )

        # Dedicated title pass fails here -> title falls back to the first-line title.
        mocker.patch(
            "services.signal_pipeline.AzureOpenAIService.generate_signal_title",
            return_value=None,
        )

        # Call brief route
        response = client.post("/api/cron/brief", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "cron-user@example.com" in data["results"]
        user_result = data["results"]["cron-user@example.com"]
        assert user_result["status"] == "success"
        assert "brief_id" in user_result
        assert user_result["articles_count"] == 1

        # Check brief is in database
        with db_session() as conn:
            brief = conn.execute("SELECT * FROM signal_briefs WHERE id = ?", (user_result["brief_id"],)).fetchone()
            assert brief is not None
            # The first-line H2 is lifted into the title and stripped from the body.
            assert brief["title"] == "Scheduled Brief Synthesis"
            assert brief["content"] == "Everything matches the Taste Profile."
            assert brief["user_id"] == user["id"]
    finally:
        if orig_secret is not None:
            os.environ["CRON_SECRET"] = orig_secret
        else:
            del os.environ["CRON_SECRET"]
