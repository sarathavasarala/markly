import json
from database import db_session, upsert_user, utc_now
from tests.test_feeds import _insert_feed, _insert_feed_item

AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}


def test_cluster_refresh_no_items(client):
    upsert_user("test@example.com", full_name="Test User")
    response = client.post("/api/clusters/refresh", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 0
    assert data["updated"] == 0
    assert data["archived"] == 0
    assert isinstance(data["clusters"], list)


def test_cluster_refresh_creates_cluster_from_similar_items(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    
    # Insert two items that should group together
    item_id1 = _insert_feed_item(
        user["id"], feed_id, id="item-1", title="AMD performance gains",
        summary="A new chip release details", status="new"
    )
    item_id2 = _insert_feed_item(
        user["id"], feed_id, id="item-2", title="AMD MI300 architecture",
        summary="A new chip architecture comparison", status="new"
    )

    # Mock CLUSTER_MIN_ARTICLES to 2 for the test
    mocker.patch("config.Config.CLUSTER_MIN_ARTICLES", 2)

    # Mock AzureOpenAIService generate_embedding to return same vector for both (making similarity 1.0)
    mock_vector = [0.1] * 1536
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_embedding",
        return_value=mock_vector
    )

    # Mock AzureOpenAIService get_signal_chat_client_and_model and responses
    mock_client = mocker.MagicMock()
    mocker.patch(
        "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
        return_value=(mock_client, "gpt-4o")
    )
    
    # Mocking first call (validation)
    mock_response_val = mocker.MagicMock()
    mock_response_val.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content=json.dumps({
            "is_real_cluster": True,
            "title": "AMD MI300 Architecture Discussion",
            "summary": "Articles covering AMD's MI300 and performance gains.",
            "topic_key": "amd-mi300",
            "confidence": 0.95,
            "reject_reason": None
        })))
    ]
    mock_client.chat.completions.create.return_value = mock_response_val

    # Trigger refresh
    response = client.post("/api/clusters/refresh", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 1
    assert data["updated"] == 0
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["title"] == "AMD MI300 Architecture Discussion"
    assert data["clusters"][0]["article_count"] == 2

    # Verify database persistence
    with db_session() as conn:
        cluster_row = conn.execute("SELECT * FROM signal_clusters WHERE user_id = ?", (user["id"],)).fetchone()
        assert cluster_row is not None
        assert cluster_row["title"] == "AMD MI300 Architecture Discussion"
        assert cluster_row["article_count"] == 2
        
        items = conn.execute("SELECT * FROM signal_cluster_items WHERE cluster_id = ?", (cluster_row["id"],)).fetchall()
        assert len(items) == 2
        item_ids = {r["feed_item_id"] for r in items}
        assert "item-1" in item_ids
        assert "item-2" in item_ids


def test_cluster_refresh_rejects_weak_llm_cluster(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    
    # Insert two items
    _insert_feed_item(
        user["id"], feed_id, id="item-1", title="AMD performance gains",
        summary="A new chip release details", status="new"
    )
    _insert_feed_item(
        user["id"], feed_id, id="item-2", title="AMD MI300 architecture",
        summary="A new chip architecture comparison", status="new"
    )

    # Mock CLUSTER_MIN_ARTICLES to 2 for the test
    mocker.patch("config.Config.CLUSTER_MIN_ARTICLES", 2)

    # Mock AzureOpenAIService generate_embedding to return same vector for both (making similarity 1.0)
    mock_vector = [0.1] * 1536
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_embedding",
        return_value=mock_vector
    )

    # Mock AzureOpenAIService get_signal_chat_client_and_model and responses
    mock_client = mocker.MagicMock()
    mocker.patch(
        "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
        return_value=(mock_client, "gpt-4o")
    )
    
    # Mock validation returning not real
    mock_response_val = mocker.MagicMock()
    mock_response_val.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content=json.dumps({
            "is_real_cluster": False,
            "title": "AMD Chips",
            "summary": "Weak connection.",
            "topic_key": "amd",
            "confidence": 0.40,
            "reject_reason": "Not related closely enough"
        })))
    ]
    mock_client.chat.completions.create.return_value = mock_response_val

    # Trigger refresh
    response = client.post("/api/clusters/refresh", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 0
    assert len(data["clusters"]) == 0


def test_cluster_refresh_attaches_new_item_to_existing_cluster(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    
    # 1. Pre-insert a cluster with one item manually
    item_id1 = _insert_feed_item(
        user["id"], feed_id, id="item-1", title="AMD performance gains",
        summary="A new chip release details", status="new"
    )
    
    mock_vector = [0.1] * 1536
    now_ts = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_clusters (
                id, user_id, title, summary, topic_key, centroid_embedding,
                status, article_count, source_count, first_seen_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                "cluster-1", user["id"], "AMD Performance", "AMD summary", "amd-perf", json.dumps(mock_vector),
                1, 1, now_ts, now_ts, now_ts, now_ts
            ),
        )
        conn.execute(
            """
            INSERT INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
            VALUES (?, ?, ?, ?)
            """,
            ("cluster-1", item_id1, 1.0, now_ts),
        )
        
    # 2. Insert a new item that is similar to the centroid
    _insert_feed_item(
        user["id"], feed_id, id="item-2", title="AMD MI300 architecture",
        summary="A new chip architecture comparison", status="new"
    )

    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_embedding",
        return_value=mock_vector
    )

    # Trigger refresh - should attach item-2 to cluster-1 without calling LLM validation
    response = client.post("/api/clusters/refresh", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["created"] == 0
    assert data["updated"] == 1
    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["id"] == "cluster-1"
    assert data["clusters"][0]["article_count"] == 2

    # Verify db membership
    with db_session() as conn:
        items = conn.execute("SELECT * FROM signal_cluster_items WHERE cluster_id = ?", ("cluster-1",)).fetchall()
        assert len(items) == 2
        item_ids = {r["feed_item_id"] for r in items}
        assert "item-1" in item_ids
        assert "item-2" in item_ids


def test_generate_cluster_report_success(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    item_id = _insert_feed_item(
        user["id"], feed_id, id="item-1", title="AMD performance gains",
        summary="A new chip release details", content="Full text content here.",
        content_format="markdown", status="new"
    )
    
    # Manual cluster insert
    now_ts = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_clusters (
                id, user_id, title, summary, topic_key, centroid_embedding,
                status, article_count, source_count, first_seen_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                "cluster-1", user["id"], "AMD Performance", "AMD summary", "amd-perf", json.dumps([0.1]*1536),
                1, 1, now_ts, now_ts, now_ts, now_ts
            ),
        )
        conn.execute(
            """
            INSERT INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
            VALUES (?, ?, ?, ?)
            """,
            ("cluster-1", item_id, 1.0, now_ts),
        )

    # Mock research and synthesis calls
    mocker.patch(
        "services.clustering.research",
        return_value=("**Context**: factual research details", ["AMD chips query"])
    )
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
        return_value="# AMD Analysis Report\nThis report analyzes AMD performance gains."
    )

    response = client.post("/api/clusters/cluster-1/reports/generate", headers=AUTH_HEADERS)
    assert response.status_code == 201
    report = response.get_json()
    assert report["cluster_id"] == "cluster-1"
    assert report["title"] == "AMD Analysis Report"
    assert "This report analyzes AMD" in report["content"]

    # Verify last_report_generated_at is updated on cluster
    with db_session() as conn:
        cluster = conn.execute("SELECT * FROM signal_clusters WHERE id = ?", ("cluster-1",)).fetchone()
        assert cluster["last_report_generated_at"] is not None


def test_generate_cluster_report_requires_cluster_owner(client, mocker):
    upsert_user("test@example.com", full_name="Test User")
    other_user = upsert_user("other@example.com", full_name="Other User")
    
    # Manual cluster insert owned by other_user
    now_ts = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_clusters (
                id, user_id, title, summary, topic_key, centroid_embedding,
                status, article_count, source_count, first_seen_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                "cluster-other", other_user["id"], "Other Performance", "Other summary", "other-perf", json.dumps([0.1]*1536),
                1, 1, now_ts, now_ts, now_ts, now_ts
            ),
        )

    # Test trying to generate report for other's cluster (authenticated as test@example.com)
    response = client.post("/api/clusters/cluster-other/reports/generate", headers=AUTH_HEADERS)
    # Expected 400 or 404
    assert response.status_code in (400, 404)


def test_cluster_report_does_not_mutate_old_report_when_new_items_arrive(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    item_id1 = _insert_feed_item(
        user["id"], feed_id, id="item-1", title="AMD performance gains",
        summary="A new chip release details", content="Full text content here.",
        content_format="markdown", status="new"
    )
    
    # Manual cluster insert
    now_ts = utc_now()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_clusters (
                id, user_id, title, summary, topic_key, centroid_embedding,
                status, article_count, source_count, first_seen_at, last_seen_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                "cluster-1", user["id"], "AMD Performance", "AMD summary", "amd-perf", json.dumps([0.1]*1536),
                1, 1, now_ts, now_ts, now_ts, now_ts
            ),
        )
        conn.execute(
            """
            INSERT INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
            VALUES (?, ?, ?, ?)
            """,
            ("cluster-1", item_id1, 1.0, now_ts),
        )

    # Mock research and synthesis calls
    mocker.patch(
        "services.clustering.research",
        return_value=("**Context**: research v1", [])
    )
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
        return_value="# AMD Analysis Report v1\nContent v1."
    )

    # Generate Report 1
    response = client.post("/api/clusters/cluster-1/reports/generate", headers=AUTH_HEADERS)
    assert response.status_code == 201
    report1 = response.get_json()

    # Now attach new item-2 to same cluster-1
    item_id2 = _insert_feed_item(
        user["id"], feed_id, id="item-2", title="AMD MI300 architecture",
        summary="Architecture compare", content="Body 2", status="new"
    )
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO signal_cluster_items (cluster_id, feed_item_id, relevance_score, added_at)
            VALUES (?, ?, 0.90, ?)
            """,
            ("cluster-1", item_id2, utc_now()),
        )
        # Update counts
        conn.execute(
            "UPDATE signal_clusters SET article_count = 2 WHERE id = ?",
            ("cluster-1",)
        )

    # Mock research and synthesis for Report 2
    mocker.patch(
        "services.clustering.research",
        return_value=("**Context**: research v2", [])
    )
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
        return_value="# AMD Analysis Report v2\nContent v2."
    )

    # Generate Report 2
    response2 = client.post("/api/clusters/cluster-1/reports/generate", headers=AUTH_HEADERS)
    assert response2.status_code == 201
    report2 = response2.get_json()

    assert report1["id"] != report2["id"]
    assert report1["title"] == "AMD Analysis Report v1"
    assert report2["title"] == "AMD Analysis Report v2"

    # Verify both exist in DB and report 1 is unmodified
    with db_session() as conn:
        db_report1 = conn.execute("SELECT * FROM signal_cluster_reports WHERE id = ?", (report1["id"],)).fetchone()
        db_report2 = conn.execute("SELECT * FROM signal_cluster_reports WHERE id = ?", (report2["id"],)).fetchone()
        assert db_report1["title"] == "AMD Analysis Report v1"
        assert db_report2["title"] == "AMD Analysis Report v2"
