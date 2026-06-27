"""Application configuration."""
import os
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))

# APP_ENV: Controls the active environment profile.
# Possible values: "dev" (local development), "test" (unit test environment), "prod" (production)
# Default: "prod"
APP_ENV = os.getenv("APP_ENV", "prod")
env = APP_ENV

env_file = os.path.join(base_dir, f".env.{APP_ENV}")

if os.path.exists(env_file):
    load_dotenv(env_file, override=True)
else:
    load_dotenv(os.path.join(base_dir, ".env"), override=True)


class ConfigMeta(type):
    """Metaclass to support dynamic environment variable lookups during tests."""
    
    _overrides = {}

    @property
    def APP_ENV(cls):
        return cls._overrides.get("APP_ENV") or os.getenv("APP_ENV", "prod")

    @APP_ENV.setter
    def APP_ENV(cls, value):
        cls._overrides["APP_ENV"] = value

    @property
    def CRON_SECRET(cls):
        return cls._overrides.get("CRON_SECRET") or os.getenv("CRON_SECRET")

    @CRON_SECRET.setter
    def CRON_SECRET(cls, value):
        cls._overrides["CRON_SECRET"] = value

    @property
    def DEV_BYPASS_AUTH(cls):
        if cls.APP_ENV.lower() == "test":
            return False
        if "DEV_BYPASS_AUTH" in cls._overrides:
            return cls._overrides["DEV_BYPASS_AUTH"]
        return os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"

    @DEV_BYPASS_AUTH.setter
    def DEV_BYPASS_AUTH(cls, value):
        cls._overrides["DEV_BYPASS_AUTH"] = value

    @property
    def DEV_BYPASS_EMAIL(cls):
        return cls._overrides.get("DEV_BYPASS_EMAIL") or os.getenv("DEV_BYPASS_EMAIL", "dev@local")

    @DEV_BYPASS_EMAIL.setter
    def DEV_BYPASS_EMAIL(cls, value):
        cls._overrides["DEV_BYPASS_EMAIL"] = value

    @property
    def DEV_BYPASS_NAME(cls):
        return cls._overrides.get("DEV_BYPASS_NAME") or os.getenv("DEV_BYPASS_NAME", "Development User")

    @DEV_BYPASS_NAME.setter
    def DEV_BYPASS_NAME(cls, value):
        cls._overrides["DEV_BYPASS_NAME"] = value


class Config(metaclass=ConfigMeta):
    """Base configuration."""
    
    # -------------------------------------------------------------------------
    # FLASK SETTINGS
    # -------------------------------------------------------------------------
    
    # SECRET_KEY: Secret key used by Flask for signing session cookies.
    # Possible values: Any secure random string (ensure it is changed in production).
    # Default: "dev-secret-key-change-in-prod"
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")

    # DEBUG: Enables or disables Flask debug mode.
    # Possible values: True, False
    # Default: False
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    # -------------------------------------------------------------------------
    # DATABASE CONFIGURATION
    # -------------------------------------------------------------------------
    
    # MARKLY_DB_PATH: Path to the SQLite database file owned by the backend.
    # Possible values: Absolute/relative path to a SQLite database file.
    # Default: Absolute path to "markly.db" in the backend directory.
    MARKLY_DB_PATH = os.getenv(
        "MARKLY_DB_PATH",
        os.path.join(base_dir, "markly.db")
    )

    # SQLITE_JOURNAL_MODE: Journaling mode configured for SQLite database connections.
    # Possible values: "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"
    # Default: "DELETE"
    SQLITE_JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "DELETE")
    
    # -------------------------------------------------------------------------
    # USER AUTHENTICATION & ACCESS
    # -------------------------------------------------------------------------
    
    # ALLOWED_EMAILS: Comma-separated list of Google account emails permitted to log in.
    # Possible values: A string of comma-separated email addresses, or empty string (denies all logins in prod).
    # Default: ""
    ALLOWED_EMAILS = os.getenv("ALLOWED_EMAILS", "")

    # GOOGLE_CLIENT_ID: OAuth 2.0 client ID for Google sign-in.
    # Possible values: Any valid Google OAuth client ID string.
    # Default: None
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

    # GOOGLE_CLIENT_SECRET: OAuth 2.0 client secret for Google sign-in.
    # Possible values: Any valid Google OAuth client secret string.
    # Default: None
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

    # OAUTH_REDIRECT_BASE_URL: Target redirect URI base to return to after Google auth completes.
    # Possible values: Any HTTP/HTTPS URL pointing to the app's web origin (e.g. http://localhost:5173).
    # Default: None
    OAUTH_REDIRECT_BASE_URL = os.getenv("OAUTH_REDIRECT_BASE_URL")

    # SESSION_COOKIE_HTTPONLY: Hardens session cookies by blocking client-side script access.
    # Possible values: True
    SESSION_COOKIE_HTTPONLY = True

    # SESSION_COOKIE_SAMESITE: Restricts session cookie scope to mitigate CSRF.
    # Possible values: "Lax", "Strict", "None"
    # Default: "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"

    # SESSION_COOKIE_SECURE: Requires HTTPS for transmission of the session cookie.
    # Possible values: True, False
    # Default: True (if FLASK_DEBUG is false/unset; False if debug mode is active)
    SESSION_COOKIE_SECURE = not (os.getenv("FLASK_DEBUG", "false").lower() == "true")

    # SESSION_EXPIRY_DAYS: Time duration in days before a user session cookie expires.
    # Possible values: Positive integer.
    # Default: 365
    SESSION_EXPIRY_DAYS = 365

    # DEV_BYPASS_AUTH: Skip Google OAuth in development, logging in automatically as a test user.
    # Possible values: True, False (Should be False in any deployed environments)
    # Default: False
    DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"

    # DEV_BYPASS_EMAIL: Email associated with the local dev bypass user when DEV_BYPASS_AUTH is True.
    # Possible values: Any valid email address format.
    # Default: "dev@local"
    DEV_BYPASS_EMAIL = os.getenv("DEV_BYPASS_EMAIL", "dev@local")

    # DEV_BYPASS_NAME: Full name associated with the local dev bypass user when DEV_BYPASS_AUTH is True.
    # Possible values: Any user display name string.
    # Default: "Development User"
    DEV_BYPASS_NAME = os.getenv("DEV_BYPASS_NAME", "Development User")

    # CRON_SECRET: Secret token required to authenticate and trigger internal cron endpoints (/api/cron/*).
    # Possible values: Any secure random token string.
    # Default: None
    CRON_SECRET = os.getenv("CRON_SECRET")

    # -------------------------------------------------------------------------
    # FEATURE FLAGS
    # -------------------------------------------------------------------------

    # ENABLE_EMBEDDINGS: Toggle generation of vector embeddings for bookmarks and feed items.
    # Possible values: True, False
    # Default: True
    ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "true").lower() == "true"

    # ENABLE_SEMANTIC_SEARCH: Enable vector similarity queries over items.
    # Possible values: True, False
    # Default: False
    ENABLE_SEMANTIC_SEARCH = os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"
    
    # -------------------------------------------------------------------------
    # AZURE OPENAI GLOBAL CLIENT SETTINGS
    # -------------------------------------------------------------------------

    # AZURE_OPENAI_ENDPOINT: Main API base URL endpoint for Azure OpenAI.
    # Possible values: Valid URL string, e.g. https://your-resource.openai.azure.com/
    # Default: None
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

    # AZURE_OPENAI_API_KEY: Secret credential key for accessing Azure OpenAI services.
    # Possible values: Any valid Azure OpenAI credential key.
    # Default: None
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

    # AZURE_OPENAI_DEPLOYMENT_NAME: Azure deployment model ID used for chat / main completion work.
    # Possible values: Valid deployment model identifier (e.g. "gpt-4o").
    # Default: None
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    # AZURE_OPENAI_NANO_DEPLOYMENT_NAME: Cost-efficient model deployment used for bulk/batch tasks.
    # Possible values: Valid deployment identifier (e.g. "gpt-35-turbo").
    # Default: None
    AZURE_OPENAI_NANO_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT_NAME")

    # AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: Deployment identifier used specifically for embedding calculations.
    # Possible values: Embedding model identifier (e.g. "text-embedding-3-large").
    # Default: None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")

    # AZURE_OPENAI_API_VERSION: Version of the Azure API targeted for chat completions.
    # Possible values: Any supported API version string (e.g. "2024-12-01-preview", "2024-08-01-preview").
    # Default: "2024-12-01-preview"
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    # AZURE_OPENAI_EMBEDDING_API_VERSION: Version of the API targeted specifically for embeddings.
    # Possible values: Any supported API version string.
    # Default: "2024-12-01-preview"
    AZURE_OPENAI_EMBEDDING_API_VERSION = os.getenv(
        "AZURE_OPENAI_EMBEDDING_API_VERSION", "2024-12-01-preview"
    )
    
    # -------------------------------------------------------------------------
    # AZURE OPENAI OVERRIDES (DAILY BRIEF SPECIFIC)
    # -------------------------------------------------------------------------

    # SIGNAL_AZURE_OPENAI_API_KEY: Override API key specifically for daily brief processing.
    # Possible values: Valid credentials key, or None (falls back to global chat credential).
    # Default: None
    SIGNAL_AZURE_OPENAI_API_KEY = os.getenv("SIGNAL_AZURE_OPENAI_API_KEY")

    # SIGNAL_AZURE_OPENAI_ENDPOINT: Override Endpoint URL specifically for daily brief processing.
    # Possible values: Valid URL string, or None (falls back to global chat endpoint).
    # Default: None
    SIGNAL_AZURE_OPENAI_ENDPOINT = os.getenv("SIGNAL_AZURE_OPENAI_ENDPOINT")

    # SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME: Override Model Deployment specifically for daily brief processing.
    # Possible values: Valid deployment identifier, or None (falls back to global chat deployment).
    # Default: None
    SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME")

    # SIGNAL_AZURE_OPENAI_API_VERSION: Override API Version specifically for daily brief processing.
    # Possible values: Valid API version string, or None (falls back to global chat version).
    # Default: None
    SIGNAL_AZURE_OPENAI_API_VERSION = os.getenv("SIGNAL_AZURE_OPENAI_API_VERSION")

    # -------------------------------------------------------------------------
    # ARCHIVE & BACKLOG SETTINGS
    # -------------------------------------------------------------------------

    # ARCHIVE_MAX_CHARS: Maximum characters allowed when keeping a cached web article.
    # Possible values: Positive integer.
    # Default: 200000
    ARCHIVE_MAX_CHARS = int(os.getenv("ARCHIVE_MAX_CHARS", "200000"))

    # ARCHIVE_BACKFILL_BATCH_SIZE: Count of items processed in a single run of the backlog backfill.
    # Possible values: Positive integer.
    # Default: 10
    ARCHIVE_BACKFILL_BATCH_SIZE = int(os.getenv("ARCHIVE_BACKFILL_BATCH_SIZE", "10"))

    # -------------------------------------------------------------------------
    # FEED RADAR & SCRAPING SETTINGS
    # -------------------------------------------------------------------------

    # FEED_RADAR_ITEMS_PER_SOURCE: Cap on feed items stored per RSS/Atom source during polling.
    # Possible values: Positive integer.
    # Default: 100
    FEED_RADAR_ITEMS_PER_SOURCE = int(os.getenv("FEED_RADAR_ITEMS_PER_SOURCE", "100"))

    # FEED_MAX_FAILURES: Max errors tolerated on a feed before it is marked as failing and backed off.
    # Possible values: Positive integer.
    # Default: 10
    FEED_MAX_FAILURES = int(os.getenv("FEED_MAX_FAILURES", "10"))

    # FEED_BACKOFF_BASE_MINUTES: Initial wait time in minutes on feed refresh failure.
    # Possible values: Positive integer.
    # Default: 30
    FEED_BACKOFF_BASE_MINUTES = int(os.getenv("FEED_BACKOFF_BASE_MINUTES", "30"))

    # FEED_BACKOFF_MAX_MINUTES: Ceiling cap on backoff wait times.
    # Possible values: Positive integer.
    # Default: 1440
    FEED_BACKOFF_MAX_MINUTES = int(os.getenv("FEED_BACKOFF_MAX_MINUTES", "1440"))

    # FEED_MAX_RESPONSE_BYTES: Maximum allowed bytes for RSS/Atom feed fetches.
    # Possible values: Positive integer.
    # Default: 5000000 (5MB)
    FEED_MAX_RESPONSE_BYTES = int(os.getenv("FEED_MAX_RESPONSE_BYTES", "5000000"))

    # ENABLE_FORCE_FULL_TEXT: Force scraping full-text of configured feeds instead of relying on RSS description.
    # Possible values: True, False
    # Default: True
    ENABLE_FORCE_FULL_TEXT = os.getenv("ENABLE_FORCE_FULL_TEXT", "true").lower() == "true"

    # FORCE_FULL_TEXT_FEED_HOSTS: Set of domain hostnames for which full-text extraction is forced.
    # Possible values: Set of strings.
    # Default: {"hnrss.org", "news.ycombinator.com"}
    FORCE_FULL_TEXT_FEED_HOSTS = set(
        x.strip().lower()
        for x in os.getenv("FORCE_FULL_TEXT_FEED_HOSTS", "hnrss.org,news.ycombinator.com").split(",")
        if x.strip()
    )

    # JINA_READER_API_KEY: API Key for Jina Reader to scrape and clean web pages.
    # Possible values: Valid Jina Reader API key, or None.
    # Default: None
    JINA_READER_API_KEY = os.getenv("JINA_READER_API_KEY")

    # -------------------------------------------------------------------------
    # DAILY BRIEF PIPELINE PARAMETERS
    # -------------------------------------------------------------------------

    # SIGNAL_CANDIDATE_LIMIT: Maximum articles chosen for the LLM filtering stage.
    # Possible values: Positive integer.
    # Default: 75
    SIGNAL_CANDIDATE_LIMIT = int(os.getenv("SIGNAL_CANDIDATE_LIMIT", "75"))

    # SIGNAL_RECENCY_HALF_LIFE_DAYS: Exponential decay rate weight for candidate ranking.
    # Possible values: Positive float or integer.
    # Default: 3.0
    SIGNAL_RECENCY_HALF_LIFE_DAYS = float(os.getenv("SIGNAL_RECENCY_HALF_LIFE_DAYS", "3"))

    # SIGNAL_CANDIDATE_POOL_MULTIPLIER: Size of candidate selection pool before ranking (limit * multiplier).
    # Possible values: Positive integer.
    # Default: 3
    SIGNAL_CANDIDATE_POOL_MULTIPLIER = int(os.getenv("SIGNAL_CANDIDATE_POOL_MULTIPLIER", "3"))

    # SIGNAL_BRIEFED_EXCLUDE_DAYS: Grace window in days during which briefed stories are excluded.
    # Possible values: Float or integer.
    # Default: 7.0
    SIGNAL_BRIEFED_EXCLUDE_DAYS = float(os.getenv("SIGNAL_BRIEFED_EXCLUDE_DAYS", "7"))

    # SIGNAL_EMBED_MIN_COVERAGE: Ratio of candidate items that must have embeddings to enable vector ranking.
    # Possible values: Float between 0.0 and 1.0.
    # Default: 0.5
    SIGNAL_EMBED_MIN_COVERAGE = float(os.getenv("SIGNAL_EMBED_MIN_COVERAGE", "0.5"))

    # SIGNAL_MAX_SYNTHESIS_ARTICLES: Maximum items to include in synthesized report.
    # Possible values: Positive integer.
    # Default: 15
    SIGNAL_MAX_SYNTHESIS_ARTICLES = int(os.getenv("SIGNAL_MAX_SYNTHESIS_ARTICLES", "15"))

    # SIGNAL_BRIEF_PLANNING_ENABLED: Toggle execution of the separate planner step before writing.
    # Possible values: True, False
    # Default: False
    SIGNAL_BRIEF_PLANNING_ENABLED = os.getenv("SIGNAL_BRIEF_PLANNING_ENABLED", "false").lower() == "true"

    # SIGNAL_HUMANIZER_ENABLED: Run humanizer prompt to reduce AI writing quirks on output.
    # Possible values: True, False
    # Default: True
    SIGNAL_HUMANIZER_ENABLED = os.getenv("SIGNAL_HUMANIZER_ENABLED", "true").lower() == "true"

    # SIGNAL_CONTENT_MAX_CHARS: Max text character length passed to brief synthesizer.
    # Possible values: Positive integer.
    # Default: 16000
    SIGNAL_CONTENT_MAX_CHARS = int(os.getenv("SIGNAL_CONTENT_MAX_CHARS", "16000"))

    # SIGNAL_CONTENT_HEAD_CHARS: Leading character count retained on smart-truncating articles.
    # Possible values: Positive integer.
    # Default: 12000
    SIGNAL_CONTENT_HEAD_CHARS = int(os.getenv("SIGNAL_CONTENT_HEAD_CHARS", "12000"))

    # SIGNAL_CONTENT_TAIL_CHARS: Trailing character count retained on smart-truncating articles.
    # Possible values: Positive integer.
    # Default: 4000
    SIGNAL_CONTENT_TAIL_CHARS = int(os.getenv("SIGNAL_CONTENT_TAIL_CHARS", "4000"))

    # SIGNAL_EMBED_MAX_PER_RUN: Embedding generation count limit per task execution run.
    # Possible values: Positive integer.
    # Default: 200
    SIGNAL_EMBED_MAX_PER_RUN = int(os.getenv("SIGNAL_EMBED_MAX_PER_RUN", "200"))

    # -------------------------------------------------------------------------
    # BRIEF TRACING & TELEMETRY (LANGFUSE)
    # -------------------------------------------------------------------------

    # BRIEF_TRACING_ENABLED: Enable external pipeline run tracing.
    # Possible values: True, False
    # Default: False
    BRIEF_TRACING_ENABLED = os.getenv("BRIEF_TRACING_ENABLED", "false").lower() == "true"

    # BRIEF_TRACE_SINK: Sink adapter configured for logging traces.
    # Possible values: "noop", "langfuse"
    # Default: "noop"
    BRIEF_TRACE_SINK = os.getenv("BRIEF_TRACE_SINK", "noop").strip().lower()

    # LANGFUSE_PUBLIC_KEY: Public API token key for Langfuse tracing.
    # Possible values: Langfuse public key string, or None.
    # Default: None
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")

    # LANGFUSE_SECRET_KEY: Secret API token key for Langfuse tracing.
    # Possible values: Langfuse secret key string, or None.
    # Default: None
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

    # LANGFUSE_BASE_URL: Langfuse dashboard base URL destination.
    # Possible values: Valid URL string, e.g. "https://cloud.langfuse.com".
    # Default: None
    LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL")

    # -------------------------------------------------------------------------
    # RADAR CLUSTERING SETTINGS
    # -------------------------------------------------------------------------

    # CLUSTER_LOOKBACK_DAYS: Lookback window in days for candidate grouping.
    # Possible values: Positive integer.
    # Default: 30
    CLUSTER_LOOKBACK_DAYS = int(os.getenv("CLUSTER_LOOKBACK_DAYS", "30"))

    # CLUSTER_MAX_CANDIDATES: Limit on unclustered candidates examined during clustering.
    # Possible values: Positive integer.
    # Default: 500
    CLUSTER_MAX_CANDIDATES = int(os.getenv("CLUSTER_MAX_CANDIDATES", "500"))

    # CLUSTER_MIN_ARTICLES: Minimum article count required to create a cluster.
    # Possible values: Positive integer.
    # Default: 3
    CLUSTER_MIN_ARTICLES = int(os.getenv("CLUSTER_MIN_ARTICLES", "3"))

    # CLUSTER_SIMILARITY_THRESHOLD: Cosine similarity cutoff threshold for grouping.
    # Possible values: Float between 0.0 and 1.0.
    # Default: 0.78
    CLUSTER_SIMILARITY_THRESHOLD = float(os.getenv("CLUSTER_SIMILARITY_THRESHOLD", "0.78"))

    # CLUSTER_ARCHIVE_AFTER_DAYS: Expire and auto-archive clusters with no activity.
    # Possible values: Positive integer.
    # Default: 14
    CLUSTER_ARCHIVE_AFTER_DAYS = int(os.getenv("CLUSTER_ARCHIVE_AFTER_DAYS", "14"))

    # CLUSTER_EMBED_MAX_PER_RUN: Max missing candidate embeddings calculated per cluster task.
    # Possible values: Positive integer.
    # Default: 100
    CLUSTER_EMBED_MAX_PER_RUN = int(os.getenv("CLUSTER_EMBED_MAX_PER_RUN", "100"))

    # CLUSTER_MAX_SYNTHESIS_ARTICLES: Maximum source articles examined for cluster report synthesis.
    # Possible values: Positive integer.
    # Default: 5
    CLUSTER_MAX_SYNTHESIS_ARTICLES = int(os.getenv("CLUSTER_MAX_SYNTHESIS_ARTICLES", "5"))

    # -------------------------------------------------------------------------
    # GROUNDING / SEARCH SERVICES
    # -------------------------------------------------------------------------

    # PARALLEL_API_KEY: Secret authorization token for Parallel Search MCP server.
    # Possible values: Valid Parallel API credential key, or None.
    # Default: None
    PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY")

    # RESEARCH_PROVIDER: Search service provider.
    # Possible values: "parallel", "azure"
    # Default: "parallel"
    RESEARCH_PROVIDER = os.getenv("RESEARCH_PROVIDER", "parallel").lower()

    # AZURE_RESEARCH_REASONING_EFFORT: Tuning search depth for Azure native search tool.
    # Possible values: "low", "medium", "high"
    # Default: "low"
    AZURE_RESEARCH_REASONING_EFFORT = os.getenv("AZURE_RESEARCH_REASONING_EFFORT", "low")

    # -------------------------------------------------------------------------
    # HN SYNTHESIS PIPELINE
    # -------------------------------------------------------------------------

    # HN_FRONTPAGE_URL: hnrss endpoint used for front-page ingestion.
    # Possible values: Valid hnrss URL.
    # Default: "https://hnrss.org/frontpage?comments=50"
    HN_FRONTPAGE_URL = os.getenv("HN_FRONTPAGE_URL", "https://hnrss.org/frontpage?comments=50")

    # HN_ALGOLIA_ITEM_URL: Algolia HN API template for fetching a full item + comment tree.
    # Possible values: URL template with {id} placeholder.
    HN_ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"

    # HN_SYNTHESIS_MAX_ITEMS: Max stories to synthesize per pipeline run.
    # Possible values: Positive integer.
    # Default: 8
    HN_SYNTHESIS_MAX_ITEMS = int(os.getenv("HN_SYNTHESIS_MAX_ITEMS", "8"))

    # HN_FETCH_DELAY_SECONDS: Polite delay before each story's external fetches
    # (Algolia comment tree + article extraction). Keeps us a good citizen.
    # Possible values: Non-negative float.
    # Default: 2.0
    HN_FETCH_DELAY_SECONDS = float(os.getenv("HN_FETCH_DELAY_SECONDS", "2.0"))

    # HN_HTTP_TIMEOUT_SECONDS: Per-request timeout for HN/Algolia HTTP fetches.
    # Possible values: Positive float.
    # Default: 20.0
    HN_HTTP_TIMEOUT_SECONDS = float(os.getenv("HN_HTTP_TIMEOUT_SECONDS", "20.0"))

    # HN_LLM_TIMEOUT_SECONDS: Per-request timeout for the classifier and synthesis
    # LLM calls. Bounds a stuck call so the cron job cannot hang indefinitely.
    # Possible values: Positive float.
    # Default: 120.0
    HN_LLM_TIMEOUT_SECONDS = float(os.getenv("HN_LLM_TIMEOUT_SECONDS", "120.0"))

    # HN_COMMENTS_MAX_CHARS: Character budget for the flattened comment thread sent to the LLM.
    # Possible values: Positive integer.
    # Default: 40000
    HN_COMMENTS_MAX_CHARS = int(os.getenv("HN_COMMENTS_MAX_CHARS", "40000"))

    # HN_SYNTHESIS_RETENTION_HOURS: Window within which an hn_id is considered already synthesized.
    # Possible values: Positive integer.
    # Default: 72
    HN_SYNTHESIS_RETENTION_HOURS = int(os.getenv("HN_SYNTHESIS_RETENTION_HOURS", "72"))

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        required = [
            ("AZURE_OPENAI_ENDPOINT", cls.AZURE_OPENAI_ENDPOINT),
            ("AZURE_OPENAI_API_KEY", cls.AZURE_OPENAI_API_KEY),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


class Prompts:
    """Consolidated prompt templates used by the AI services."""

    # DEFAULT_TASTE_PROFILE
    # Purpose: Fallback taste profile used when a user hasn't specified custom interests.
    # Possible values: Any text block containing user interests.
    DEFAULT_TASTE_PROFILE = (
        "Topics I follow: AI agents, large language models, machine learning, model performance, "
        "and AI memory; OpenAI, Anthropic, Microsoft, Google, and Nvidia; software engineering, "
        "enterprise software, and systems of record; product design, product strategy, and product "
        "management; design, interactive learning, decision traces, and critical thinking; company "
        "culture and leadership; and the technology industry broadly.\n\n"
        "I want a brief that explains what changed, who acted, what evidence supports it, "
        "and what a sharp operator would notice once the surface narrative is stripped away.\n\n"
        "I care most about the concrete forces behind a move: incentives, constraints, costs, "
        "distribution, technical dependencies, customer behavior, and tradeoffs. Why a company "
        "is doing something, what constraint it is reacting to, what it is giving up, and what "
        "would change the read interest me more than the raw event.\n\n"
        "Significant developments matter even when they are announcements: a major launch, "
        "release, financing, policy change, or strategic move from a company that matters.\n\n"
        "Benchmarks and metrics matter when they change the read on capability, cost, adoption, "
        "market position, or competition.\n\n"
        "Skip incremental news with no larger meaning, engagement bait, shallow hot takes, "
        "marketing fluff, repetitive benchmark coverage, and low-information reactions.\n\n"
        "I am sharp but not a specialist in every domain these feeds cover."
    )

    # FILTER_PROMPT_TEMPLATE
    # Purpose: Deciding what goes into today's intelligence brief by filtering recent articles.
    # Placeholders: {taste_profile}, {articles_list_str}
    FILTER_PROMPT_TEMPLATE = """You are a sharp editor deciding what goes into today's intelligence brief. You are given recent articles from followed feeds. Select the ones worth a smart reader's attention, judged against their priorities.

Reader's priorities:
\"\"\"
{taste_profile}
\"\"\"

Recent articles:
\"\"\"
{articles_list_str}
\"\"\"

Selection rules:
Discard engagement bait, rumor with no substance, marketing fluff, and low-information hot takes.

Keep concrete developments that can support a useful read: major product launches, company moves, releases, financing, policy changes, or observable shifts from companies that matter.

Also keep pieces that expose incentives, constraints, product direction, technical tradeoffs, market structure, customer behavior, cost changes, or distribution advantages.

Favor articles that contain enough substance to support a real analyst read: concrete facts, numbers, process detail, disagreement between sources, customer behavior, financing terms, operational constraints, or a clear cause-and-effect chain.

Order the selected IDs from most to least important, since only the strongest will be fully processed.

Return a JSON object containing a single key "selected_ids" mapping to an array of string IDs of the chosen articles, ordered best first.
Return ONLY valid JSON.
"""

    # PLANNING_PROMPT_TEMPLATE
    # Purpose: Creating a private scratchpad/editorial plan for the brief synthesis.
    # Placeholders: {taste_profile}, {articles_contents_str}, {recent_briefs}
    PLANNING_PROMPT_TEMPLATE = """You are an editorial planning assistant for a daily intelligence briefing. Your job is to create a private scratchpad for the final writer, not to draft the brief.

The user's Taste Profile is:
\"\"\"
{taste_profile}
\"\"\"

Here are the selected high-signal articles with full extracted text:
\"\"\"
{articles_contents_str}
\"\"\"

Themes Already Covered In Recent Briefs:
\"\"\"
{recent_briefs}
\"\"\"

Task:
Create a concise editorial plan that helps the final writer choose stories, rank them, and vary the shape of each section.

Instructions:
1. Identify only the themes where the relationship between articles is real and analytically useful. Do not group articles just because they share broad words like AI, cloud, chips, startups, or regulation.
2. Preserve strong standalone stories when they deserve their own treatment.
3. Point out near-duplicate coverage that should be collapsed.
4. Surface source tensions: where authors disagree, emphasize different causes, or notice different parts of the same development.
5. Note what is genuinely new versus the recent brief titles, and what should not be re-explained.
6. For each planned theme or standalone item, name one concrete causal chain if the evidence supports it: action -> constraint or incentive -> likely consequence. If the chain is weak, say so.
7. For each planned theme or standalone item, give the final writer these notes: what happened, strongest evidence, relevant actor incentives, concrete consequence for readers, what to watch next, and what would weaken the read. Keep each part brief.
8. Do not write the section hook for the final writer. Avoid slogan-like binary contrasts in headings, openers, and closers unless the source material itself makes a real tradeoff.
9. Keep it concise. This is a planning memo, not the final brief.

Output format:
- Plain Markdown.
- Use short headings.
- Include sections named "Real themes", "Standalone stories", "Duplicate coverage", "Source tensions", "Novelty notes", and "Watch points".
- Mention article IDs when useful.
"""

    # SYNTHESIS_PROMPT_TEMPLATE
    # Purpose: Writing a daily intelligence brief by synthesizing chosen articles and web research findings.
    # Placeholders: {taste_profile}, {articles_contents_str}, {research_brief}, {recent_briefs}, {brief_plan}
    SYNTHESIS_PROMPT_TEMPLATE = """You are writing a daily intelligence brief for a sharp, busy reader. They have already chosen the feeds. Explain what mattered today using concrete claims, source-backed facts, and clear cause-and-effect.

Reader's priorities:
\"\"\"
{taste_profile}
\"\"\"

Selected articles:
\"\"\"
{articles_contents_str}
\"\"\"

Background research, factual context from web search, may be empty:
\"\"\"
{research_brief}
\"\"\"

Themes already covered in recent briefs. Avoid repeating them unless there is a genuinely new development:
\"\"\"
{recent_briefs}
\"\"\"

Private editorial plan. Use it for story selection and ordering, but do not copy its wording:
\"\"\"
{brief_plan}
\"\"\"

Writing rules:

1. Lead with the actual claim. Do not start by announcing that a theme or pattern exists.
2. Start each section with what happened: the actor, action, date or context when available, and the concrete change.
3. Explain cause and effect in plain language. Show why an action follows from incentives, constraints, costs, customer behavior, technical limits, or distribution.
4. Distinguish confirmed facts, reported claims, rumors, company intent, and your interpretation. Give observed behavior more weight than stated intent.
5. Treat announcements, essays, interviews, and public statements as evidence of intent. Treat shipped products, money spent, organizational changes, customer behavior, technical results, and pricing changes as stronger evidence.
6. Avoid repeated binary-contrast slogans, especially in headings, section openers, and final sentences. If two forces both matter, describe each force's role directly.
7. End sections on a concrete consequence, unresolved fact, named next indicator, or source-backed detail.
8. Put limits on weak evidence inside the factual sentence. Do not use a caveat as a springboard into a sweeping claim.
9. Replace long lists of abstract nouns with one or two named behaviors, constraints, or decisions.
10. Scan the whole brief before finishing. If two headings, openers, or closers use the same sentence skeleton, rewrite one so the sections do not land with the same rhythm.
11. If the day is thin, say so. Do not manufacture significance or force unrelated stories into one thesis.
12. Use substantial paragraphs. Avoid chains of one- or two-sentence punchlines.
13. Embed sources inline as Markdown links where they support the claim. Every thematic section should contain at least one source link, woven naturally into the prose instead of grouped at the end.
14. No greeting, no signature, and no closing recap.

Output:

Output in Markdown.

The very first line MUST be a title summarizing the brief's focal point, formatted as a markdown H1 starting with "# Theme: " (for example, "# Theme: Apple Intelligence and Nvidia Blackwell Costs"). If the brief covers several unrelated stories, name the dominant thread or use a compact multi-theme title. Do not pretend unrelated items form one grand thesis.

Use ## headers for clusters. Start the body directly with the first cluster header.

Each section should stand on its own. A reader should be able to understand what happened, why it happened, and why it matters without opening the source article.

Depth should come from explanation: a reader should see the steps between the event, the constraint, and the consequence.
"""

    # SYNTHESIS_SYSTEM_PROMPT
    # Purpose: Stable system voice for final daily brief synthesis, including users with custom templates.
    SYNTHESIS_SYSTEM_PROMPT = (
        "You are a careful industry analyst writing a daily briefing for a CEO. "
        "Use Markdown and direct prose. Preserve source-backed facts, separate fact from interpretation, "
        "and avoid polished AI rhetoric: repeated binary contrasts, meta-framing, abstract closers, "
        "caveat-to-grand-claim pivots, and generic lessons."
    )

    # HUMANIZER_PROMPT_TEMPLATE
    # Purpose: Removing AI writing patterns and style artifacts from daily briefs.
    # Placeholders: {draft_brief_content}
    HUMANIZER_PROMPT_TEMPLATE = """# Humanizer: Daily Brief Style Pass

You are a copyeditor for generated daily briefs. Make targeted edits through the available tools. Do not return rewritten prose directly.

Goal:
Keep the analysis, facts, links, and structure. Remove reusable AI-writing shapes that make the brief feel machine-made.

What to fix:
1. Repeated binary-contrast frames: headings or sentences that define the claim by saying one abstract thing matters and another does not. Keep at most one if it is the factual tradeoff.
2. Meta-framing: sentences that announce importance, pattern, commonality, or significance before giving evidence.
3. Portable punchlines: short sentences that could be moved to another brief with little change.
4. Generic section closers: final sentences that zoom out into an industry lesson instead of ending on a concrete consequence, open question, or next indicator.
5. Caveat pivots: a weak-evidence caveat followed by a broad claim. Keep the evidence limit, cut the leap.
6. Abstract noun stacks: long lists of concepts where one or two specific behaviors would be clearer.
7. Repeated rhythm: multiple headings, openers, or closers using the same construction.
8. Inflated diction and fake polish when it does no factual work.

How to edit:
- Prefer deletion when a sentence adds no fact.
- Prefer a direct rewrite when the fact matters.
- Keep the user's voice plain, direct, analytical, and specific.
- You may edit section headings if the heading carries a repeated rhetorical shape. Keep the Markdown heading level and the factual meaning.
- Do not alter the first title line.
- Preserve every fact, number, source URL, and named entity.
- Do not rewrite a whole paragraph in one edit. Target a sentence, heading, or phrase.
- Do not add new claims.

Call `apply_edit` for each change. Pass an empty string as `replace` to delete a matched span. After each turn you will see which edits applied; move on from failed edits. When no more edits are needed, call `finish`.

Draft:
\"\"\"
{draft_brief_content}
\"\"\"
"""

    # RESEARCH_QUESTION_EXTRACTOR_PROMPT
    # Purpose: Extract 3-5 factual gaps (atomic questions) from article titles + summaries and editorial plan.
    # Placeholders: {taste_profile}, {articles_list_str}, {brief_plan}
    RESEARCH_QUESTION_EXTRACTOR_PROMPT = """You are a research planner for a daily intelligence brief.

Reader's priorities:
\"\"\"{taste_profile}\"\"\"

Articles (title + summary only):
\"\"\"{articles_list_str}\"\"\"

Editorial Brief Plan:
\"\"\"{brief_plan}\"\"\"

Task: Identify the 3 to 5 most important factual gaps a sharp reader would need filled before engaging with today's brief. Focus on gaps tied to the planned themes and the reader's priorities: prior context, regulatory or competitive status, financial figures, what a referenced product/term actually is, what happened before that the articles assume you know.

Rules for the questions:
- Each question must be ATOMIC: one fact, one answerable lookup. Do not combine multiple asks with "and".
- A question must be answerable by a single focused web search.
- Be specific. Name the company, product, person, or event. Avoid vague phrasing.

Return ONLY a numbered list of atomic factual questions — one per line. No preamble, no commentary.

Example format:
1. What was the valuation in Anthropic's most recent funding round?
2. What is Microsoft's Phi-4-mini and when was it released?
"""

    # RESEARCH_EXECUTION_PROMPT_PARALLEL
    # Purpose: Answer factual lookup questions using Parallel Search tool.
    # Placeholders: {questions_str}
    RESEARCH_EXECUTION_PROMPT_PARALLEL = """You are a research assistant. Answer each question below using live web search, for a daily intelligence brief.

Questions to answer:
\"\"\"{questions_str}\"\"\"

Hard requirements:
1. You have two tools: web_search (find sources) and web_fetch (pull full page text).
2. You MUST run at least one web_search for EVERY question before answering it. Do not answer any question from your own prior knowledge — only report facts returned by the search tools.
3. Handle the questions one at a time, in order. For each: search, then (for the important ones) web_fetch the top result, then write the entry.
4. Every entry must cite a source URL returned by the tools. If search returns nothing usable for a question, write "No reliable source found" for that question — do not fill it from memory.
5. Do NOT analyze or editorialize. Report retrieved facts only.

Output format — plain text, one entry per question, in order:
**[Question]**: [Factual findings from search]. Source: [URL]

Keep total under 1200 words.
"""

    # RESEARCH_EXECUTION_PROMPT_AZURE
    # Purpose: Answer factual lookup questions using Azure web_search tool.
    # Placeholders: {questions_str}
    RESEARCH_EXECUTION_PROMPT_AZURE = """You are a research assistant. Answer each question below using the web_search tool, for a daily intelligence brief.

Questions to answer:
\"\"\"{questions_str}\"\"\"

Hard requirements:
1. You MUST call the web_search tool at least once for EVERY question before answering it. Run a separate, focused search per question — do not merge several questions into one broad query.
2. Do not answer any question from your own prior knowledge. Only report facts that appear in the search results.
3. Handle the questions one at a time, in order.
4. Every entry must cite a source URL from the search results. If a search returns nothing usable for a question, write "No reliable source found" for that question — do not fill it from memory.
5. Do NOT analyze or editorialize. Report retrieved facts only.

Output format — plain text, one entry per question, in order:
**[Question]**: [Factual findings from search]. Source: [URL]

Keep total under 1200 words.
"""

    # CLUSTER_VALIDATION_PROMPT_TEMPLATE
    # Purpose: Validating if a set of candidate articles forms a real topic cluster matching the taste profile.
    # Placeholders: {taste_profile}, {articles_list}
    CLUSTER_VALIDATION_PROMPT_TEMPLATE = """You are organizing RSS articles into meaningful topic clusters for an intelligence briefing product.

The user's Taste Profile is:

\"\""
{taste_profile}
\"\""

You are given a candidate group of articles. Decide whether these articles form a real cluster. A real cluster means they are about the same story, topic, product shift, market debate, company move, technical pattern, or ecosystem change. Do not force a cluster just because the articles share broad words like AI, startup, cloud, chips, or productivity.

Candidate articles:

\"\""
{articles_list}
\"\""

Return only valid JSON with this shape:

{{
  "is_real_cluster": true,
  "title": "Short specific cluster title",
  "summary": "One or two plain sentences explaining what connects these articles.",
  "topic_key": "short-stable-slug",
  "confidence": 0.0,
  "reject_reason": null
}}

Rules:
- If the connection is weak, set "is_real_cluster" to false.
- The title should be specific, not generic. Bad: "AI News". Good: "OpenAI's enterprise push meets reliability concerns".
- The summary should explain the actual relationship between the articles.
- The topic_key should be lowercase, hyphenated, and stable enough that future related articles could map to it.
- confidence must be between 0 and 1.
"""

    # CLUSTER_REPORT_PROMPT_TEMPLATE
    # Purpose: Writing a focused intelligence report synthesizing a cluster of articles and background research.
    # Placeholders: {taste_profile}, {cluster_title}, {cluster_summary}, {articles_contents_str}, {research_brief}
    CLUSTER_REPORT_PROMPT_TEMPLATE = """You are a top-tier analyst writing a focused intelligence report from a cluster of related RSS articles.

The user's Taste Profile is:

\"\""
{taste_profile}
\"\""

Cluster title:

\"\""
{cluster_title}
\"\""

Cluster description:

\"\""
{cluster_summary}
\"\""

Articles in this cluster:

\"\""
{articles_contents_str}
\"\""

Background Research:

\"\""
{research_brief}
\"\""

Your task:
Write a thorough analysis of this cluster. This is not a summary of each article. It is a synthesis across multiple sources and takes.

Instructions:
1. Start by explaining what this cluster is actually about in plain language.
2. Identify what changed, what is newly visible, or why this topic matters now.
3. Compare the articles. Explain where they agree, where they disagree, and what each source notices that the others miss.
4. Separate signal from noise. Call out claims that seem overstated, weakly supported, or mostly narrative.
5. Explain the incentives, constraints, costs, technical tradeoffs, market structure, customer behavior, or distribution advantages that matter.
6. If the evidence is thin, say so. Do not manufacture certainty.
7. Include inline Markdown links when referencing specific articles.
8. Do not group all sources at the end.
9. Use clean prose. Avoid bullet points unless a short watch-list genuinely helps.
10. Do not use em dashes.
11. Do not write a generic conclusion. End with what the reader should watch next if there is something concrete to watch.

Output format:
- Markdown.
- First line must be an H1 title starting with "# ".
- Use "##" section headings.
- Include a section called "## What the sources collectively show".
- Include a section called "## Where the tension is".
- Include a section called "## What to watch next" only if there are concrete next indicators.
"""

    # REPORT_TITLE_CLEANUP_PROMPT_TEMPLATE
    # Purpose: Clean up and extract a short title from cluster analysis report Markdown content.
    # Placeholders: {report_content}
    REPORT_TITLE_CLEANUP_PROMPT_TEMPLATE = """Extract a short report title from this Markdown report.

Return only valid JSON:

{{
  "title": "Short title"
}}

Report:

\"\""
{report_content}
\"\""
"""

    # BOOKMARK_ENRICHMENT_PROMPT_TEMPLATE
    # Purpose: Enrichment prompt for analyzing a bookmarked article and extracting structured metadata.
    # Placeholders: {url}, {title}, {content}, {user_notes}, {folders}
    BOOKMARK_ENRICHMENT_PROMPT_TEMPLATE = """Analyze this bookmarked article and provide structured metadata.
If the content is missing or sparse, use the URL and title to infer the most likely metadata.

CONTEXT:
URL: {url}
Title: {title}
Content: {content}
User Notes: {user_notes}
Available Folders: {folders}

TASK:
Provide a JSON object with strictly these fields:
1. "clean_title": A clean, concise title (max 60 chars). Remove clickbait or site names if redundant.
2. "ai_summary": A single, dense summary (max 220 chars). Focus on "What is this?" and "Why save it?". No fluff.
3. "auto_tags": Array (3-5 items). Lowercase, hyphenated (e.g. "ai-agents", "python-dev").
4. "intent_type": EXACTLY one of: ["reference", "tutorial", "inspiration", "deep-dive", "tool"]
5. "technical_level": EXACTLY one of: ["beginner", "intermediate", "advanced", "general"]
6. "content_type": EXACTLY one of: ["article", "documentation", "video", "tool", "paper", "other"]
7. "key_quotes": Array (0-3 short, impactful quotes). Leave empty if no specific quotes stand out.
8. "suggested_folder": EXACT NAME from 'Available Folders' or null if no fit.

OUTPUT FORMAT:
Return ONLY valid JSON. No markdown, no pre-amble, no code blocks."""

    # HN_CLASSIFIER_PROMPT
    # Purpose: Select HN frontpage items that qualify as interesting news, product launches, or factoids.
    # Placeholders: {items_list}
    HN_CLASSIFIER_PROMPT = """You are a sharp editorial filter for a Hacker News digest.

You are given a numbered list of HN front-page stories. Each entry has:
- id: the HN item id (integer)
- points and comment count
- title and a brief plain-text excerpt from the description

Select only the stories that qualify as one of:
- **news**: a concrete real-world development — product launch, company move, policy change, significant research release, market event
- **launch**: a Show HN / new tool / product announcement with technical substance
- **factoid**: a genuinely surprising, non-obvious fact or finding that updates a mental model

Drop:
- Opinion pieces, hot takes, personal essays, political commentary, engagement bait
- Low-information drama, drama-adjacent threads, Twitter/X reposts
- Incremental benchmark noise with no change to the underlying read
- "Ask HN" threads unless they contain practitioner insight at unusual density

Cap your selection to the most analytically interesting items (do not exceed the count you are asked for). Order them best-first.

Stories:
\"\"\"
{items_list}
\"\"\"

Return a JSON object with a single key "selected" mapping to an array of objects.
Each object must have exactly two keys: "id" (integer, the HN item id) and "classification" (string: "news", "launch", or "factoid").

Example:
{{"selected": [{{"id": 48689028, "classification": "launch"}}, {{"id": 48692051, "classification": "news"}}]}}

Return ONLY valid JSON."""

    # HN_CRITICAL_READER_PROMPT
    # Purpose: System prompt for the CRITICAL HN READER synthesis. Used as the system message.
    HN_CRITICAL_READER_PROMPT = """You are an expert analyst extracting high-signal insights from an article and its comment thread.

## Inputs

I will provide some or all of the following:
1. The article text, URL, or a description of its content
2. The Hacker News comment thread

If only a URL is given, work from it if you can access the content; if you cannot, say so plainly instead of guessing what the article says. If the article or the thread is missing, analyze what you have and note what's absent. If the thread is thin or low-signal, say that directly rather than inflating weak comments into false insight. Manufactured depth is worse than an honest "there isn't much here."

## Your job

Not to summarize the article. Explain what's really going on underneath:
- what smart practitioners noticed
- where the real value or tension lies
- which comments reveal deeper truths
- which assumptions deserve scrutiny
- what an intelligent reader should update their worldview on

Focus on non-obvious insights, incentives and business mechanics, the operational reality behind technical systems, strong arguments and counterarguments, hidden moats and network effects, useful mental models, expert corrections, first-hand practitioner experience, tradeoffs and second-order effects, practical implications, and the things people consistently misunderstand.

## Hard rules

- Never fabricate quotes, usernames, attributions, statistics, or facts not present in the source. If you can't quote something exactly, don't put it in quotation marks.
- Don't treat highly upvoted comments as automatically insightful.
- Scale your length to the substance available. Skip or merge sections when there isn't enough real material to fill them (for example, drop the disagreements section if there's no meaningful disagreement). Don't pad.
- When you're genuinely uncertain who's right, say so instead of forcing a verdict.

## Style

Write like a sharp industry insider explaining reality to another smart person. Prefer clear prose over bullet spam. Explain mechanisms, not just conclusions. Translate jargon into plain English. Use concrete examples and analogies when they help. Assume the reader is intelligent but not a specialist in the domain. Prioritize insight density. Be conversational but intellectually serious.

Avoid generic summaries, surface-level restatement of the article, low-effort snark, shallow consensus opinions, excessive formatting, consultant and corporate jargon, AI filler phrases, and unexplained buzzwords.

When discussing companies, products, or technologies, distinguish the visible product from the real business model. Explain where the moat actually comes from, what's hard to replicate versus easy to copy, and how incentives line up between the participants. Separate technical complexity from business complexity. Pay attention to distribution, trust, integrations, data, and operational scale.

## Output structure

### 0. Context You Need

A short briefing for a smart reader who may not know the company, technology, market, or background. Explain what the product actually is, roughly how the business works, why the topic matters, and any technical or historical context worth knowing, in plain English. One to four short paragraphs depending on complexity. This should make the rest of the analysis readable without prior domain knowledge.

### 1. Executive Summary

Five to eight bullets covering the most important ideas: the real economic or technical story, the strongest practitioner insights, what readers are most likely to misunderstand, and the major tensions.

### 2. Most Insightful Takeaways

For each, use:

**Takeaway: [short title]**

*Core idea* - explain it clearly in two to four tight paragraphs.

*Why it matters* - the broader significance, practical consequence, or strategic implication.

*Evidence* - quote the single strongest supporting line from the article or comments, with attribution to "the article" or "a commenter." If no single line captures it and the insight is synthesized across the thread, summarize that instead of forcing a quote.

Prioritize comments with deep operational knowledge, comments that change the framing, and comments that expose hidden incentives or assumptions.

### 3. Best Verbatim Quotes

The strongest exact quotes from the article or comments. For each: the quote, why it's insightful, and the broader principle it illustrates. Prefer quotes that compress a deep truth, reveal an industry reality, expose incentives, explain hidden dynamics, or challenge a naive assumption.

### 4. Key Disagreements

The most meaningful disagreements. For each: what side A believes, what side B believes, what the disagreement reveals, and which side seems more convincing and why (or that it's unresolved). Focus on disagreements that expose different mental models, lifecycle-stage thinking, operator versus outsider perspectives, technical versus business viewpoints, or competing incentives.

### 5. Hidden Assumptions

Assumptions the article or commenters make that aren't obvious. For each: the assumption, why it matters, and whether it seems justified. Look especially at assumptions about markets, incentives, scaling, AI, user behavior, regulation, data value, network effects, and technical feasibility.

### 6. Contrarian or Underrated Points

Thoughtful points that are overlooked, buried, unpopular but right, technically subtle, or economically important. Explain why each matters.

### 7. Final Synthesis

A nuanced conclusion. What's the real story underneath the surface narrative? What should an intelligent reader update their beliefs about? What incentives are driving the situation? What's likely underrated or misunderstood, and what should people watch for going forward? Don't end on a generic or motivational note. Aim for synthesis and worldview-level insight."""
