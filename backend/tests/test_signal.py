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
    from config import Config

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

    mock_response_filter = mocker.MagicMock()
    mock_response_filter.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content='{"selected_ids": ["item-1"]}'))
    ]

    if Config.SIGNAL_BRIEF_PLANNING_ENABLED:
        mock_response_plan = mocker.MagicMock()
        mock_response_plan.choices = [
            mocker.MagicMock(message=mocker.MagicMock(content="Real themes\n- Reliability is becoming the product story."))
        ]
        mock_client.chat.completions.create.side_effect = [mock_response_filter, mock_response_plan]
    else:
        mock_client.chat.completions.create.side_effect = [mock_response_filter]

    # Mocking research call
    mock_research = mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_research_with_search",
        return_value=("**Concept**: factual grounding", ["query 1"])
    )

    # Mocking synthesis call
    mock_synthesis = mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
        return_value="## AI Ecosystem Shift\nAI labs are optimizing for reliability and deployment economics — which is a major change."
    )

    mocker.patch(
        "services.signal_pipeline.style_edit_brief",
        side_effect=lambda x, *args, **kwargs: x,
    )

    # Generate brief
    response = client.post("/api/signal/briefs", headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    # Verify em-dashes are post-processed/replaced with " - "
    assert "reliability and deployment economics - which" in data["content"]
    # The first-line H2 is lifted into the title and stripped from the body.
    assert data["title"] == "AI Ecosystem Shift"
    assert "## AI Ecosystem Shift" not in data["content"]

    if Config.SIGNAL_BRIEF_PLANNING_ENABLED:
        research_prompt = mock_research.call_args.args[0]
        synthesis_prompt = mock_synthesis.call_args.args[0]
        assert "Reliability is becoming the product story" in research_prompt
        assert "Reliability is becoming the product story" in synthesis_prompt

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
        "signal_synthesis_limit": 10,
        "signal_filter_prompt": "Custom filter prompt {taste_profile} {articles_list_str}",
        "signal_planning_prompt": "Custom planning prompt {taste_profile} {articles_contents_str}",
        "signal_synthesis_prompt": "Custom synthesis prompt {taste_profile} {articles_contents_str}"
    }

    response = client.put("/api/signal/taste-profile", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["taste_profile"] == payload["taste_profile"]
    assert data["signal_candidate_limit"] == 50
    assert data["signal_synthesis_limit"] == 10
    assert data["signal_filter_prompt"] == payload["signal_filter_prompt"]
    assert data["signal_planning_prompt"] == payload["signal_planning_prompt"]
    assert data["signal_synthesis_prompt"] == payload["signal_synthesis_prompt"]

    # Verify retrieval
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["taste_profile"] == payload["taste_profile"]
    assert data["signal_candidate_limit"] == 50
    assert data["signal_synthesis_limit"] == 10
    assert data["signal_filter_prompt"] == payload["signal_filter_prompt"]
    assert data["signal_planning_prompt"] == payload["signal_planning_prompt"]
    assert data["signal_synthesis_prompt"] == payload["signal_synthesis_prompt"]


def test_reset_taste_profile_customizations(client):
    upsert_user("test@example.com", full_name="Test User")
    payload = {
        "taste_profile": "",
        "signal_candidate_limit": None,
        "signal_synthesis_limit": None,
        "signal_filter_prompt": "",
        "signal_planning_prompt": "",
        "signal_synthesis_prompt": ""
    }

    response = client.put("/api/signal/taste-profile", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    
    # When reset, taste_profile falls back to default, limit is null/None, templates are null/None
    assert "I want analysis, not summaries" in data["taste_profile"]
    assert data["signal_candidate_limit"] is None
    assert data["signal_synthesis_limit"] is None
    assert data["signal_filter_prompt"] is None
    assert data["signal_planning_prompt"] is None
    assert data["signal_synthesis_prompt"] is None

    # Retrieve and verify default templates are returned as defaults, but custom columns are null
    response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.get_json()
    assert "I want analysis, not summaries" in data["taste_profile"]
    assert data["signal_candidate_limit"] is None
    assert data["signal_synthesis_limit"] is None
    assert data["signal_filter_prompt"] is None
    assert data["signal_planning_prompt"] is None
    assert data["signal_synthesis_prompt"] is None
    assert "You are a sharp editor" in data["default_filter_prompt"]
    assert "editorial planning assistant" in data["default_planning_prompt"]
    assert "You are writing a daily intelligence brief" in data["default_synthesis_prompt"]


def test_taste_profile_reports_planning_feature_flag(client):
    from config import Config

    upsert_user("test@example.com", full_name="Test User")
    original = Config.SIGNAL_BRIEF_PLANNING_ENABLED
    try:
        Config.SIGNAL_BRIEF_PLANNING_ENABLED = False
        response = client.get("/api/signal/taste-profile", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.get_json()["signal_planning_enabled"] is False
    finally:
        Config.SIGNAL_BRIEF_PLANNING_ENABLED = original


def test_signal_pipeline_research_and_synthesize(mocker):
    from services.signal_pipeline import research, synthesize

    # 1. Test research(web_search_enabled=False) returns ("", [])
    assert research([], web_search_enabled=False) == ("", [])

    # 2. Test research(web_search_enabled=True) calls generate_research_with_search
    mock_research = mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_research_with_search",
        return_value=("My research brief", ["query 1"])
    )
    brief, queries = research([{"id": "1", "title": "A", "feed_title": "B", "url": "http://a", "content": "body"}], web_search_enabled=True, brief_plan="Plan context")
    assert brief == "My research brief"
    assert queries == ["query 1"]
    mock_research.assert_called_once()
    assert "Plan context" in mock_research.call_args.args[0]

    # 3. Test synthesize formatting and fallback
    mock_synthesis = mocker.patch(
        "services.openai_service.AzureOpenAIService.generate_brief_with_verbosity",
        return_value="synthesis brief content"
    )
    # Custom template with research_brief placeholder
    res = synthesize(
        selected_items=[{"id": "1", "title": "A", "feed_title": "B", "url": "http://a", "content": "body"}],
        taste_profile="taste instructions",
        synthesis_template="Brief: {taste_profile} Research: {research_brief}",
        research_brief="test research",
        brief_plan="test plan"
    )
    assert res == "synthesis brief content"
    mock_synthesis.assert_called_once_with(
        "Brief: taste instructions Research: test research",
        "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown.",
        verbosity="medium"
    )

    # 4. Test synthesize with custom template WITHOUT research_brief placeholder (safe formatter handles it)
    mock_synthesis.reset_mock()
    res = synthesize(
        selected_items=[{"id": "1", "title": "A", "feed_title": "B", "url": "http://a", "content": "body"}],
        taste_profile="taste instructions",
        synthesis_template="Brief: {taste_profile}",
        research_brief="test research"
    )
    assert res == "synthesis brief content"
    mock_synthesis.assert_called_once_with(
        "Brief: taste instructions",
        "You are a thoughtful industry analyst writing briefings for a CEO. Always write in clean prose and format in Markdown.",
        verbosity="medium"
    )


def test_extract_queries_from_item():
    from services.openai_service import AzureOpenAIService

    # 1. Test native web_search_call structure
    item_native = {
        "type": "web_search_call",
        "action": {"query": "latest news about GPT-5"}
    }
    assert AzureOpenAIService._extract_queries_from_item(item_native) == ["latest news about GPT-5"]

    # 2. Test general tool_call at top level
    item_tool = {
        "type": "tool_call",
        "tool_type": "web_search",
        "arguments": '{"query": "Claude 3.7 Sonnet capabilities"}'
    }
    assert AzureOpenAIService._extract_queries_from_item(item_tool) == ["Claude 3.7 Sonnet capabilities"]

    # 3. Test general function_call with arguments dict
    item_func = {
        "type": "function_call",
        "name": "web_search",
        "arguments": {"query": "Nvidia Blackwell yield delays"}
    }
    assert AzureOpenAIService._extract_queries_from_item(item_func) == ["Nvidia Blackwell yield delays"]

    # 4. Test message with nested tool_call contents
    item_message = {
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "output_text", "text": "Analyzing terms..."},
            {
                "type": "tool_call",
                "tool_call": {
                    "name": "web_search",
                    "arguments": '{"query": "Apple vision pro sales stats"}'
                }
            }
        ]
    }
    assert AzureOpenAIService._extract_queries_from_item(item_message) == ["Apple vision pro sales stats"]

    # 5. Test recursive fallback with nested lists/dicts
    item_recursive = {
        "type": "some_other_type",
        "nested_list": [
            {
                "random_key": {
                    "type": "function_call",
                    "name": "web_search",
                    "arguments": {"queries": ["query A", "query B"]}
                }
            }
        ]
    }
    assert AzureOpenAIService._extract_queries_from_item(item_recursive) == ["query A", "query B"]

    # 6. Test mcp_call structures
    # A. With objective (preferred)
    item_mcp_objective = {
        "type": "mcp_call",
        "arguments": {
            "objective": "Find latest public information on Anthropic sandboxing",
            "search_queries": ["Anthropic engineering", "Claude containment"]
        }
    }
    assert AzureOpenAIService._extract_queries_from_item(item_mcp_objective) == ["Find latest public information on Anthropic sandboxing"]

    # B. With search_queries fallback (when objective is missing)
    item_mcp_queries = {
        "type": "mcp_call",
        "arguments": {
            "search_queries": ["Anthropic engineering", "Claude containment"]
        }
    }
    assert AzureOpenAIService._extract_queries_from_item(item_mcp_queries) == ["Anthropic engineering", "Claude containment"]

    # C. With arguments as JSON string
    item_mcp_string = {
        "type": "mcp_call",
        "arguments": '{"objective": "Find latest public information on Anthropic sandboxing"}'
    }
    assert AzureOpenAIService._extract_queries_from_item(item_mcp_string) == ["Find latest public information on Anthropic sandboxing"]

    # 7. Test web_fetch and fetch calls with url parameters
    item_mcp_url = {
        "type": "mcp_call",
        "arguments": {
            "url": "https://example.com/nvidia-blackwell"
        }
    }
    assert AzureOpenAIService._extract_queries_from_item(item_mcp_url) == ["Fetch: https://example.com/nvidia-blackwell"]

    item_tool_url = {
        "type": "tool_call",
        "tool_type": "web_fetch",
        "arguments": '{"url": "https://example.com/claude-3-7"}'
    }
    assert AzureOpenAIService._extract_queries_from_item(item_tool_url) == ["Fetch: https://example.com/claude-3-7"]



def test_generate_research_with_search_success(mocker):
    from services.openai_service import AzureOpenAIService
    from config import Config

    # Mock endpoint/key config
    Config.AZURE_OPENAI_ENDPOINT = "https://my-endpoint.openai.azure.com"
    Config.AZURE_OPENAI_API_KEY = "my-key"
    Config.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o"
    Config.PARALLEL_API_KEY = "parallel-key"

    # Mock successful requests.post response
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "output": [
            {
                "type": "mcp_call",
                "arguments": {
                    "objective": "Find latest Nvidia news"
                }
            },
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Factual research brief content"}
                ]
            }
        ]
    }
    
    mock_post = mocker.patch("requests.post", return_value=mock_response)
    
    brief, queries = AzureOpenAIService.generate_research_with_search("prompt", "instructions")
    
    assert brief == "Factual research brief content"
    assert queries == ["Find latest Nvidia news"]
    mock_post.assert_called_once()
    
    # Check that headers and data sent to requests.post are correct
    args, kwargs = mock_post.call_args
    assert kwargs["headers"]["api-key"] == "my-key"
    assert "https://search.parallel.ai/mcp" in kwargs["json"]["tools"][0]["server_url"]
    assert kwargs["json"]["tools"][0]["headers"]["Authorization"] == "Bearer parallel-key"


def test_generate_research_with_search_api_failure_fallback(mocker):
    from services.openai_service import AzureOpenAIService
    from config import Config

    Config.AZURE_OPENAI_ENDPOINT = "https://my-endpoint.openai.azure.com"
    Config.AZURE_OPENAI_API_KEY = "my-key"
    Config.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4o"

    # Mock Requests post failure
    mock_post = mocker.patch("requests.post", side_effect=Exception("API Timeout"))

    # Mock fallback standard chat completion client
    mock_openai_client = mocker.MagicMock()
    mocker.patch(
        "services.openai_service.AzureOpenAIService.get_chat_client",
        return_value=mock_openai_client
    )
    mock_completion_res = mocker.MagicMock()
    mock_completion_res.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content="standard fallback brief"))
    ]
    mock_openai_client.chat.completions.create.return_value = mock_completion_res

    brief, queries = AzureOpenAIService.generate_research_with_search("prompt", "instructions")

    assert brief == "standard fallback brief"
    assert queries == []
    mock_post.assert_called_once()
    mock_openai_client.chat.completions.create.assert_called_once()


def test_generate_brief_with_verbosity_success(mocker):
    from services.openai_service import AzureOpenAIService
    from config import Config

    # Reset any SIGNAL-specific environment overrides to force fallback to standard endpoints
    Config.SIGNAL_AZURE_OPENAI_ENDPOINT = None
    Config.SIGNAL_AZURE_OPENAI_API_KEY = None
    Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = None

    Config.AZURE_OPENAI_ENDPOINT = "https://my-endpoint.openai.azure.com"
    Config.AZURE_OPENAI_API_KEY = "my-key"
    Config.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-5"

    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Detailed daily brief content with high verbosity"}
                ]
            }
        ]
    }
    
    mock_post = mocker.patch("requests.post", return_value=mock_response)
    
    brief = AzureOpenAIService.generate_brief_with_verbosity("prompt", "instructions", verbosity="high")
    
    assert brief == "Detailed daily brief content with high verbosity"
    mock_post.assert_called_once()
    
    args, kwargs = mock_post.call_args
    assert kwargs["headers"]["api-key"] == "my-key"
    assert kwargs["json"]["text"]["verbosity"] == "high"
    assert "tools" not in kwargs["json"]


def test_generate_brief_with_verbosity_fallback(mocker):
    from services.openai_service import AzureOpenAIService
    from config import Config

    # Reset any SIGNAL-specific environment overrides to force fallback to standard endpoints
    Config.SIGNAL_AZURE_OPENAI_ENDPOINT = None
    Config.SIGNAL_AZURE_OPENAI_API_KEY = None
    Config.SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = None

    Config.AZURE_OPENAI_ENDPOINT = "https://my-endpoint.openai.azure.com"
    Config.AZURE_OPENAI_API_KEY = "my-key"
    Config.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-5"

    # Mock post error to trigger fallback
    mock_post = mocker.patch("requests.post", side_effect=Exception("API Error"))
    
    # Mock fallback standard chat completion client
    mock_openai_client = mocker.MagicMock()
    mocker.patch(
        "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
        return_value=(mock_openai_client, "gpt-5")
    )
    mock_completion_res = mocker.MagicMock()
    mock_completion_res.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content="fallback standard completions brief"))
    ]
    mock_openai_client.chat.completions.create.return_value = mock_completion_res

    brief = AzureOpenAIService.generate_brief_with_verbosity("prompt", "instructions", verbosity="high")

    assert brief == "fallback standard completions brief"
    mock_post.assert_called_once()
    mock_openai_client.chat.completions.create.assert_called_once()


def test_generate_brief_stream_success(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    _insert_feed_item(
        user["id"],
        feed_id,
        id="item-1",
        title="AI reliability vs benchmarks",
        summary="A summary",
        content="Full text content",
        content_format="html",
        status="new"
    )

    # Mock pipeline functions to isolate route logic
    mocker.patch("services.signal_pipeline.load_user_settings", return_value={
        "taste_profile": "custom taste",
        "candidate_limit": 10,
        "filter_template": "filter {taste_profile}",
        "planning_template": "plan {taste_profile}",
        "synthesis_template": "synthesis {taste_profile}",
        "web_search_enabled": True
    })

    # Mock extract_contents generator
    def mock_extract_generator(selected_items):
        yield (1, 1)
        return []

    mocker.patch("services.signal_pipeline.llm_filter", return_value=[{"id": "item-1", "title": "AI reliability vs benchmarks", "feed_title": "B", "url": "http://a", "content": "Full text content"}])
    mocker.patch("services.signal_pipeline.extract_contents", side_effect=mock_extract_generator)
    mocker.patch("services.signal_pipeline.persist_content_updates")
    mocker.patch("services.signal_pipeline.plan_brief", return_value="Brief plan details")
    mocker.patch("services.signal_pipeline.research", return_value=("Background details", ["query 1"]))
    mocker.patch("services.signal_pipeline.synthesize", return_value="The final daily brief.")
    mocker.patch("services.signal_pipeline.style_edit_brief", side_effect=lambda x, *args, **kwargs: x)
    mocker.patch("services.signal_pipeline.save_brief", return_value={"id": "brief-123", "content": "The final daily brief."})

    response = client.post("/api/signal/briefs/generate", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/event-stream"

    # Read the streamed events
    data = response.get_data(as_text=True)
    events = [line for line in data.split("\n") if line.startswith("data:")]
    
    assert len(events) >= 8
    import json
    parsed_events = [json.loads(e.removeprefix("data: ")) for e in events]
    stages = [evt["stage"] for evt in parsed_events]
    
    assert "scanning" in stages
    assert "filtering" in stages
    assert "filtered" in stages
    assert "extracting" in stages
    assert "planning" in stages
    assert "planned" in stages
    assert "researching" in stages
    assert "researched" in stages
    assert "synthesizing" in stages
    assert "humanizing" in stages
    assert "complete" in stages

    # Verify telemetry word counts are calculated and streamed
    scanning_evt = next(evt for evt in parsed_events if evt["stage"] == "scanning")
    assert "candidate_word_count" in scanning_evt
    assert scanning_evt["candidate_word_count"] > 0

    filtered_evt = next(evt for evt in parsed_events if evt["stage"] == "filtered")
    assert "candidate_word_count" in filtered_evt
    assert filtered_evt["candidate_word_count"] > 0

    researching_evt = next(evt for evt in parsed_events if evt["stage"] == "researching")
    assert "extracted_word_count" in researching_evt
    assert researching_evt["extracted_word_count"] > 0

    planned_evt = next(evt for evt in parsed_events if evt["stage"] == "planned")
    assert "plan_word_count" in planned_evt
    assert planned_evt["plan_word_count"] > 0

    researched_evt = next(evt for evt in parsed_events if evt["stage"] == "researched")
    assert "research_word_count" in researched_evt
    assert researched_evt["research_word_count"] > 0
    assert "extracted_word_count" in researched_evt

    synthesizing_evt = next(evt for evt in parsed_events if evt["stage"] == "synthesizing")
    assert "synthesis_word_count" in synthesizing_evt
    assert synthesizing_evt["synthesis_word_count"] > 0
    assert "extracted_word_count" in synthesizing_evt
    assert "plan_word_count" in synthesizing_evt
    assert "research_word_count" in synthesizing_evt

    complete_evt = next(evt for evt in parsed_events if evt["stage"] == "complete")
    assert "synthesis_output_word_count" in complete_evt
    assert complete_evt["synthesis_output_word_count"] > 0


def test_generate_brief_stream_skips_planning_when_feature_disabled(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    _insert_feed_item(
        user["id"],
        feed_id,
        id="item-1",
        title="AI reliability vs benchmarks",
        summary="A summary",
        content="Full text content",
        content_format="html",
        status="new"
    )

    mocker.patch("services.signal_pipeline.load_user_settings", return_value={
        "taste_profile": "custom taste",
        "candidate_limit": 10,
        "filter_template": "filter {taste_profile}",
        "planning_template": "plan {taste_profile}",
        "planning_enabled": False,
        "synthesis_template": "synthesis {taste_profile}",
        "web_search_enabled": True
    })

    def mock_extract_generator(selected_items):
        yield (1, 1)
        return []

    mock_plan = mocker.patch("services.signal_pipeline.plan_brief", return_value="Brief plan details")
    mock_research = mocker.patch("services.signal_pipeline.research", return_value=("Background details", ["query 1"]))
    mock_synthesize = mocker.patch("services.signal_pipeline.synthesize", return_value="The final daily brief.")
    mocker.patch("services.signal_pipeline.style_edit_brief", side_effect=lambda x, *args, **kwargs: x)
    mocker.patch("services.signal_pipeline.llm_filter", return_value=[{"id": "item-1", "title": "AI reliability vs benchmarks", "feed_title": "B", "url": "http://a", "content": "Full text content"}])
    mocker.patch("services.signal_pipeline.extract_contents", side_effect=mock_extract_generator)
    mocker.patch("services.signal_pipeline.persist_content_updates")
    mocker.patch("services.signal_pipeline.save_brief", return_value={"id": "brief-123", "content": "The final daily brief."})

    response = client.post("/api/signal/briefs/generate", headers=AUTH_HEADERS)
    assert response.status_code == 200

    import json
    events = [line for line in response.get_data(as_text=True).split("\n") if line.startswith("data:")]
    parsed_events = [json.loads(e.removeprefix("data: ")) for e in events]
    stages = [evt["stage"] for evt in parsed_events]

    assert "planning" not in stages
    assert "planned" not in stages
    assert "researching" in stages
    assert "synthesizing" in stages
    mock_plan.assert_not_called()
    assert mock_research.call_args.kwargs["brief_plan"] == ""
    assert mock_synthesize.call_args.kwargs["brief_plan"] == ""


def test_signal_telemetry_logging(client, mocker):
    user = upsert_user("test@example.com", full_name="Test User")
    feed_id = _insert_feed(user["id"])
    _insert_feed_item(
        user["id"],
        feed_id,
        id="item-telemetry-1",
        title="Telemetry Test Item",
        summary="A summary",
        content="Full content",
        content_format="html",
        status="new"
    )

    # Mock settings and mock a failure in llm_filter
    mocker.patch("services.signal_pipeline.load_user_settings", return_value={
        "taste_profile": "custom taste",
        "candidate_limit": 10,
        "filter_template": "filter {taste_profile}",
        "planning_template": "plan {taste_profile}",
        "synthesis_template": "synthesis {taste_profile}",
        "web_search_enabled": True
    })
    mocker.patch("services.signal_pipeline.llm_filter", side_effect=ValueError("LLM Service Unavailable"))

    # Generate brief stream (should fail during filtering)
    response = client.post("/api/signal/briefs/generate", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/event-stream"

    # Read events to check if "error" stage was reached
    data = response.get_data(as_text=True)
    events = [line for line in data.split("\n") if line.startswith("data:")]
    assert len(events) > 0
    
    import json
    parsed_events = [json.loads(e.removeprefix("data: ")) for e in events]
    stages = [evt["stage"] for evt in parsed_events]
    assert "error" in stages
    
    error_evt = next(evt for evt in parsed_events if evt["stage"] == "error")
    assert "Failed during filtering: LLM Service Unavailable" in error_evt["message"]

    # Verify that the telemetry database log exists
    with db_session() as conn:
        row = conn.execute("SELECT * FROM telemetry_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user["id"],)).fetchone()
        assert row is not None
        assert row["stage"] == "filtering"
        assert row["error_message"] == "LLM Service Unavailable"
        assert "ValueError" in row["traceback"]

    # Check querying via the API route
    response_telemetry = client.get("/api/signal/telemetry", headers=AUTH_HEADERS)
    assert response_telemetry.status_code == 200
    telemetry_data = response_telemetry.get_json()
    assert "telemetry" in telemetry_data
    assert len(telemetry_data["telemetry"]) >= 1
    assert telemetry_data["telemetry"][0]["stage"] == "filtering"
    assert telemetry_data["telemetry"][0]["error_message"] == "LLM Service Unavailable"


def test_parse_and_clean_brief():
    from services.signal_pipeline import parse_and_clean_brief

    # 1. Test # Theme: format
    content_1 = "# Theme: Apple Intelligence Shifts\n\n## Section 1\nSome content here."
    title, clean = parse_and_clean_brief(content_1)
    assert title == "Apple Intelligence Shifts"
    assert clean == "## Section 1\nSome content here."

    # 2. Test #Theme: format (no space)
    content_2 = "#Theme: Nvidia Blackwell Costs\nSome content here."
    title, clean = parse_and_clean_brief(content_2)
    assert title == "Nvidia Blackwell Costs"
    assert clean == "Some content here."

    # 3. Test generic # format
    content_3 = "# Tech Innovations 2026\n## Cluster A\nDetails."
    title, clean = parse_and_clean_brief(content_3)
    assert title == "Tech Innovations 2026"
    assert clean == "## Cluster A\nDetails."

    # 4. Test first-line H2 is treated as the title (matches database.py backfill).
    # Briefs in practice put their main title on the first line as `## ...`.
    content_4 = "## Cluster A\nDetails without main title."
    title, clean = parse_and_clean_brief(content_4)
    assert title == "Cluster A"
    assert clean == "Details without main title."

    # 5. Test clean formatting (e.g. bold wrappers inside header title)
    content_5 = "# Theme: **AMD MI300 Performance**\nContent here."
    title, clean = parse_and_clean_brief(content_5)
    assert title == "AMD MI300 Performance"
    assert clean == "Content here."


def test_save_brief_with_title():
    from database import db_session, upsert_user
    from services.signal_pipeline import save_brief

    user = upsert_user("test@example.com", full_name="Test User")
    content = "# Theme: My Dynamic Title\n\n## Subtheme\nBody details"

    with db_session() as conn:
        brief = save_brief(conn, user["id"], content, [])
        assert brief["title"] == "My Dynamic Title"
        assert brief["content"] == "## Subtheme\nBody details"

        row = conn.execute("SELECT * FROM signal_briefs WHERE id = ?", (brief["id"],)).fetchone()
        assert row["title"] == "My Dynamic Title"
        assert row["content"] == "## Subtheme\nBody details"


def test_load_recent_brief_titles_and_builder():
    from database import db_session, upsert_user, new_id
    from services.signal_pipeline import load_recent_brief_titles, _build_recent_briefs_str

    user = upsert_user("recent@example.com", full_name="Recent User")
    with db_session() as conn:
        # Empty case
        assert load_recent_brief_titles(conn, user["id"]) == []
        assert "first brief" in _build_recent_briefs_str([]).lower()

        # Insert three briefs with increasing timestamps; newest-first ordering expected.
        for idx, t in enumerate(["Oldest", "Middle", "Newest"]):
            conn.execute(
                "INSERT INTO signal_briefs (id, user_id, content, title, article_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (new_id(), user["id"], "body", t, 1, f"2026-06-1{idx} 00:00:00"),
            )
        conn.commit()

        titles = load_recent_brief_titles(conn, user["id"], limit=2)
        assert titles == ["Newest", "Middle"]
        built = _build_recent_briefs_str(titles)
        assert "- Newest" in built and "- Middle" in built


def test_style_edit_brief_disabled():
    from services.signal_pipeline import style_edit_brief
    from config import Config

    orig_enabled = Config.SIGNAL_HUMANIZER_ENABLED
    Config.SIGNAL_HUMANIZER_ENABLED = False

    try:
        result = style_edit_brief("Draft content", "Template: {draft_brief_content}")
        assert result == "Draft content"
    finally:
        Config.SIGNAL_HUMANIZER_ENABLED = orig_enabled


def test_style_edit_brief_applies_edits(mocker):
    """Agent calls apply_edit twice then finish; both edits are applied."""
    from services.signal_pipeline import style_edit_brief
    from config import Config
    import json

    orig_enabled = Config.SIGNAL_HUMANIZER_ENABLED
    Config.SIGNAL_HUMANIZER_ENABLED = True

    def _tc(call_id, fn_name, fn_args_dict):
        """Build a tool_call mock with a correctly addressable .function.name."""
        fn = mocker.MagicMock()
        fn.name = fn_name
        fn.arguments = json.dumps(fn_args_dict)
        tc = mocker.MagicMock()
        tc.id = call_id
        tc.function = fn
        return tc

    try:
        mock_client = mocker.MagicMock()
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_client, "gpt-4o")
        )

        draft = "This stands as a testament to innovation. It showcases vibrant results."

        # Turn 1: two apply_edit calls
        turn1_msg = mocker.MagicMock()
        turn1_msg.content = None
        turn1_msg.tool_calls = [
            _tc("call_1", "apply_edit", {
                "reason": "AI cliche",
                "search": "stands as a testament to innovation",
                "replace": "shows the team's focus",
            }),
            _tc("call_2", "apply_edit", {
                "reason": "promotional language",
                "search": "showcases vibrant results",
                "replace": "produced clear results",
            }),
        ]

        # Turn 2: finish
        turn2_msg = mocker.MagicMock()
        turn2_msg.content = None
        turn2_msg.tool_calls = [
            _tc("call_3", "finish", {"summary": "Removed two AI cliches."}),
        ]

        mock_client.chat.completions.create.side_effect = [
            mocker.MagicMock(choices=[mocker.MagicMock(message=turn1_msg)]),
            mocker.MagicMock(choices=[mocker.MagicMock(message=turn2_msg)]),
        ]

        result = style_edit_brief(draft, "{draft_brief_content}")

        assert "shows the team's focus" in result
        assert "produced clear results" in result
        assert "testament to innovation" not in result
        assert mock_client.chat.completions.create.call_count == 2
    finally:
        Config.SIGNAL_HUMANIZER_ENABLED = orig_enabled


def test_style_edit_brief_skip_on_failed_patch(mocker):
    """An edit whose search string can't be found is silently skipped."""
    from services.signal_pipeline import style_edit_brief
    from config import Config
    import json

    orig_enabled = Config.SIGNAL_HUMANIZER_ENABLED
    Config.SIGNAL_HUMANIZER_ENABLED = True

    def _tc(call_id, fn_name, fn_args_dict):
        fn = mocker.MagicMock()
        fn.name = fn_name
        fn.arguments = json.dumps(fn_args_dict)
        tc = mocker.MagicMock()
        tc.id = call_id
        tc.function = fn
        return tc

    try:
        mock_client = mocker.MagicMock()
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_client, "gpt-4o")
        )

        draft = "Original draft content here."

        # Turn 1: edit with text that does NOT exist in the draft
        turn1_msg = mocker.MagicMock()
        turn1_msg.content = None
        turn1_msg.tool_calls = [
            _tc("call_1", "apply_edit", {
                "reason": "test",
                "search": "text that does not exist",
                "replace": "replacement",
            }),
        ]

        # Turn 2: finish
        turn2_msg = mocker.MagicMock()
        turn2_msg.content = None
        turn2_msg.tool_calls = [
            _tc("call_2", "finish", {"summary": "nothing changed"}),
        ]

        mock_client.chat.completions.create.side_effect = [
            mocker.MagicMock(choices=[mocker.MagicMock(message=turn1_msg)]),
            mocker.MagicMock(choices=[mocker.MagicMock(message=turn2_msg)]),
        ]

        result = style_edit_brief(draft, "{draft_brief_content}")

        # Draft must be unchanged since the edit couldn't be applied
        assert result == draft
    finally:
        Config.SIGNAL_HUMANIZER_ENABLED = orig_enabled


def test_style_edit_brief_error_fallback(mocker):
    """If the LLM call raises, return the original draft unchanged."""
    from services.signal_pipeline import style_edit_brief
    from config import Config

    orig_enabled = Config.SIGNAL_HUMANIZER_ENABLED
    Config.SIGNAL_HUMANIZER_ENABLED = True

    try:
        mock_client = mocker.MagicMock()
        mocker.patch(
            "services.openai_service.AzureOpenAIService.get_signal_chat_client_and_model",
            return_value=(mock_client, "gpt-4o")
        )
        mock_client.chat.completions.create.side_effect = Exception("API error")

        result = style_edit_brief("Draft content", "{draft_brief_content}")
        assert result == "Draft content"
    finally:
        Config.SIGNAL_HUMANIZER_ENABLED = orig_enabled
