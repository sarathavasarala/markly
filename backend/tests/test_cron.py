import os
from database import upsert_user


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


def test_cron_brief_queues_jobs(client, mocker):
    # Set the CRON_SECRET
    orig_secret = os.getenv("CRON_SECRET")
    os.environ["CRON_SECRET"] = "super-secret-cron-token"
    headers = {"Authorization": "Bearer super-secret-cron-token"}

    try:
        mock_enqueue = mocker.patch(
            "routes.cron.brief_jobs.enqueue_daily_brief_jobs",
            return_value={"queued": 1, "existing": 0},
        )
        mock_start_worker = mocker.patch("routes.cron.brief_jobs.start_worker")

        response = client.post("/api/cron/brief", headers=headers)
        assert response.status_code == 202
        data = response.get_json()
        assert data["success"] is True
        assert data == {"success": True, "status": "queued", "queued": 1, "existing": 0}
        mock_enqueue.assert_called_once_with()
        mock_start_worker.assert_called_once_with()
    finally:
        if orig_secret is not None:
            os.environ["CRON_SECRET"] = orig_secret
        else:
            del os.environ["CRON_SECRET"]
