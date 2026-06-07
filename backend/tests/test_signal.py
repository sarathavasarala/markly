from database import db_session, upsert_user, utc_now
from tests.test_feeds import _insert_feed, _insert_feed_item

AUTH_HEADERS = {"Authorization": "Bearer dummy-token"}

def test_get_taste_profile_default(client):
    upsert_user("test@example.com", full_name="Test User")
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert "taste_profile" in data
    assert "I want analysis, not summaries" in data["taste_profile"]

def test_update_taste_profile(client):
    upsert_user("test@example.com", full_name="Test User")
    new_profile = "My custom instructions for the analyst."
    
    # Update profile
    response = client.put("/api/signal/taste-profile", json={"taste_profile": new_profile}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    
    # Retrieve to verify persistence
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.get_json()["taste_profile"] == new_profile

def test_list_briefs(client):
    user = upsert_user("test@example.com", full_name="Test User")
    
    # Insert a dummy brief directly
    now = utc_now()
    with db_session() as conn:
        conn.execute(
            "INSERT INTO signal_briefs (id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
            ("brief-1", user["id"], "Brief Content", now)
        )
    
    response = client.get("/api/signal/briefs", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["briefs"]) == 1
    assert data["briefs"][0]["id"] == "brief-1"
    assert data["briefs"][0]["content"] == "Brief Content"

def test_generate_brief_no_content(client):
    upsert_user("test@example.com", full_name="Test User")
    response = client.post("/api/signal/briefs", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is False
    assert data["reason"] == "no_content"
    assert "No recent RSS feed content found" in data["message"]

def test_generate_brief_success(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    item_id = _insert_feed_item(
        user["id"],
        feed_id,
        id="item-1",
        title="AI reliability vs benchmarks",
        summary="A summary about model releases",
        content="Full text about AI labs reliability and enterprise software economics",
        content_format="html",
        status="new"
    )

    # Mock AzureOpenAIService get_signal_chat_client_and_model and responses
    mock_client = mocker.MagicMock()
    mocker.patch(
        "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
        return_value=(mock_client, "gpt-4o")
    )
    
    # Mocking first call (filtering)
    mock_response_filter = mocker.MagicMock()
    mock_response_filter.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content='{"selected_ids": ["item-1"]}'))
    ]
    
    mock_client.chat.completions.create.side_effect = [mock_response_filter]
    
    # Mocking synthesis call
    mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_search",
        return_value="## AI Ecosystem Shift\nAI labs are optimizing for reliability and deployment economics — which is a major change."
    )

    # Generate brief
    response = client.post("/api/signal/briefs", headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    # Verify em-dashes are post-processed/replaced with " - "
    assert "reliability and deployment economics - which" in data["content"]
    assert "## AI Ecosystem Shift" in data["content"]

    # Verify item status remains new (not auto-dismissed)
    with db_session() as conn:
        row = conn.execute("SELECT status FROM feed_items WHERE id = ?", (item_id,)).fetchone()
        assert row["status"] == "new"

    # Verify brief is stored
    response = client.get("/api/signal/briefs", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.get_json()["briefs"]) == 1

def test_signal_custom_llm_settings(mocker):
    from config import Config
    from services.openai_service import AzureOpenAIService
    
    # Clear cached clients to start clean
    AzureOpenAIService._chat_client = None
    AzureOpenAIService._signal_chat_client = None
    
    # Save original configurations
    orig_key = Config.SIGNAL_AZURE_OPENAI_API_KEY
    orig_endpoint = Config.SIGNAL_AZURE_OPENAI_ENDPOINT
    orig_deployment = Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME
    orig_version = Config.SIGNAL_AZURE_OPENAI_API_VERSION
    
    try:
        # 1. Without overrides, should return default client and default model
        Config.SIGNAL_AZURE_OPENAI_API_KEY = None
        Config.SIGNAL_AZURE_OPENAI_ENDPOINT = None
        Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = None
        Config.SIGNAL_AZURE_OPENAI_API_VERSION = None
        
        mock_chat_client = mocker.MagicMock()
        mocker.patch.object(AzureOpenAIService, "get_chat_client", return_value=mock_chat_client)
        
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        assert client == mock_chat_client
        assert model == Config.AZURE_OPENAI_DEPLOYMENT_NAME
        
        # 2. With overrides, should initialize a new client and return the custom model
        AzureOpenAIService._signal_chat_client = None
        
        Config.SIGNAL_AZURE_OPENAI_API_KEY = "test-signal-key"
        Config.SIGNAL_AZURE_OPENAI_ENDPOINT = "https://test-signal-endpoint.openai.azure.com"
        Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o-custom"
        Config.SIGNAL_AZURE_OPENAI_API_VERSION = "2024-08-01-preview"
        
        mock_custom_client = mocker.MagicMock()
        mock_init = mocker.patch("services.openai_service.AzureOpenAI", return_value=mock_custom_client)
        
        client, model = AzureOpenAIService.get_signal_chat_client_and_model()
        assert model == "gpt-4o-custom"
        assert client == mock_custom_client
        mock_init.assert_called_once_with(
            api_version="2024-08-01-preview",
            azure_endpoint="https://test-signal-endpoint.openai.azure.com",
            api_key="test-signal-key"
        )
    finally:
        # Restore original configurations
        Config.SIGNAL_AZURE_OPENAI_API_KEY = orig_key
        Config.SIGNAL_AZURE_OPENAI_ENDPOINT = orig_endpoint
        Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = orig_deployment
        Config.SIGNAL_AZURE_OPENAI_API_VERSION = orig_version
        
        # Clear cached clients
        AzureOpenAIService._chat_client = None
        AzureOpenAIService._signal_chat_client = None


def test_update_taste_profile_customizations(client):
    upsert_user("test@example.com", full_name="Test User")
    payload = {
        "taste_profile": "My custom taste profile instructions.",
        "signal_candidate_limit": 50,
        "signal_filter_prompt": "Custom filter prompt {taste_profile} {articles_list_str}",
        "signal_synthesis_prompt": "Custom synthesis prompt {taste_profile} {articles_contents_str}"
    }

    response = client.put("/api/signal/taste-profile", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["taste_profile"] == payload["taste_profile"]
    assert data["signal_candidate_limit"] == 50
    assert data["signal_filter_prompt"] == payload["signal_filter_prompt"]
    assert data["signal_synthesis_prompt"] == payload["signal_synthesis_prompt"]

    # Verify retrieval
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["taste_profile"] == payload["taste_profile"]
    assert data["signal_candidate_limit"] == 50
    assert data["signal_filter_prompt"] == payload["signal_filter_prompt"]
    assert data["signal_synthesis_prompt"] == payload["signal_synthesis_prompt"]


def test_reset_taste_profile_customizations(client):
    upsert_user("test@example.com", full_name="Test User")
    payload = {
        "taste_profile": "",
        "signal_candidate_limit": None,
        "signal_filter_prompt": "",
        "signal_synthesis_prompt": ""
    }

    response = client.put("/api/signal/taste-profile", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    
    # When reset, taste_profile falls back to default, limit is null/None, templates are null/None
    assert "I want analysis, not summaries" in data["taste_profile"]
    assert data["signal_candidate_limit"] is None
    assert data["signal_filter_prompt"] is None
    assert data["signal_synthesis_prompt"] is None

    # Retrieve and verify default templates are returned as defaults, but custom columns are null
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert "I want analysis, not summaries" in data["taste_profile"]
    assert data["signal_candidate_limit"] is None
    assert data["signal_filter_prompt"] is None
    assert data["signal_synthesis_prompt"] is None
    assert "You are an expert analyst assistant." in data["default_filter_prompt"]
    assert "You are a top-tier analyst" in data["default_synthesis_prompt"]
