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
        "I want analysis, not summaries: what actually changed, why it matters, and what "
        "sharp operators or practitioners would notice beneath the surface narrative.\n\n"
        "I care most about strategic implications, incentives, product direction, business "
        "mechanics, technical tradeoffs, ecosystem shifts, and second-order effects. Why a "
        "company is doing something, what constraints it is reacting to, what hidden incentives "
        "exist, and what longer pattern a move represents interest me more than the raw event.\n\n"
        "Significant developments matter even when they are announcements: a major launch, "
        "release, financing, policy change, or strategic move from a company that matters.\n\n"
        "A benchmark or metric only interests me when it signals something broader about "
        "capability, economics, adoption, market position, or competitive dynamics. Numbers for "
        "their own sake do not.\n\n"
        "What I do not value: incremental news with no larger meaning, engagement bait, shallow "
        "hot takes, marketing fluff, repetitive benchmark coverage, and low-information reactions.\n\n"
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
Discard engagement bait, rumor with no substance, marketing fluff, low-information hot takes, and the tenth rewrite of a story already covered elsewhere in the list.

Keep genuinely significant developments even when they are announcements. A major product launch, a strategic move, a notable release, a financing, a policy change, or a real shift from a company that matters belongs in the brief when the implications are analyzable.

Also keep pieces with genuine insight, real strategic relevance, ecosystem shifts, product direction, business mechanics, technical constraints, market structure, incentives, or important second-order implications.

Favor articles that contain enough substance to support a real analyst read: concrete facts, numbers, process detail, disagreement between sources, customer behavior, financing terms, operational constraints, or a mechanism worth unpacking.

It is fine to select few. A short list of strong items beats a padded one. If little qualifies today, return a short list.

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
Create a concise editorial plan that helps the final brief have more depth and less forced grouping.

Instructions:
1. Identify only the themes where the relationship between articles is real and analytically useful. Do not group articles just because they share broad words like AI, cloud, chips, startups, or regulation.
2. Preserve strong standalone stories when they deserve their own treatment.
3. Point out near-duplicate coverage that should be collapsed.
4. Surface source tensions: where authors disagree, emphasize different mechanisms, or notice different parts of the same development.
5. Note what is genuinely new versus the recent brief titles, and what should not be re-explained.
6. For each planned theme or standalone item, explain the mechanism the final writer should investigate: incentives, constraints, technical tradeoffs, business mechanics, ecosystem shifts, or second-order effects.
7. For each planned theme or standalone item, give the final writer a concrete angle in this shape: what happened, why it matters, evidence strength, what to watch next, and what would weaken the read. Keep each part brief.
8. Flag a contrast only where the source material genuinely supports one. Leave framing and phrasing choices to the final writer.
9. Keep it concise. This is a planning memo, not the final brief.

Output format:
- Plain Markdown.
- Use short headings.
- Include sections named "Real themes", "Standalone stories", "Duplicate coverage", "Source tensions", "Novelty notes", and "Watch points".
- Mention article IDs when useful.
"""

    # SYNTHESIS_PROMPT_TEMPLATE
    # Purpose: Writing a daily intelligence brief by synthesizing chosen articles and web research findings.
    # Placeholders: {taste_profile}, {articles_contents_str}, {research_brief}, {recent_briefs}
    SYNTHESIS_PROMPT_TEMPLATE = """You are writing a daily intelligence brief for a sharp, busy reader. They have already chosen the feeds. Your job is to explain what actually mattered today and why.

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

=========================================================
HOW TO THINK
=========================================================

Your value is judgment, not coverage.

Start with the facts. Explain what happened, who did what, and what changed. Assume the reader has not read the source material.

Before discussing implications, explain how the underlying system works. The reader should understand the mechanism before being asked to care about the consequences.

Move carefully from facts to interpretation. State what happened before explaining what it may mean. Make clear whether you are describing evidence, offering an interpretation, or discussing a possible future consequence.

When discussing organizations, focus on incentives and constraints. What are they optimizing for? What problem are they trying to solve? What tradeoffs are they accepting? Why might this decision be rational from their perspective?

Actively look for alternative explanations. If a smart skeptic could interpret the evidence differently, acknowledge that and explain why you prefer one interpretation over another, or why the evidence remains inconclusive.

Explain second-order effects only when you can trace a credible mechanism. Show how one thing leads to another. Do not treat speculation as foresight.

Follow the money whenever useful. Ask who pays, who benefits, who bears risk, who captures value, and what must be true economically for the strategy to work.

Treat announcements, essays, interviews, and public statements primarily as evidence of intent. Give more weight to products shipped, money spent, organizational changes, customer behavior, technical results, and observed actions.

Do not mistake a coherent narrative for a real trend. Before describing something as a major shift, consider whether the available evidence actually supports that claim.

If the day is thin, say so. Do not manufacture significance.

=========================================================
FRAMING
=========================================================

Write to explain reality, not to demonstrate insight.

Do not manufacture significance. When two things both matter, treat both as real rather than elevating one by dismissing the other; that is a reasoning shortcut, not an insight.

Do not force unrelated stories into a single narrative.

Do not overclaim. A development is not automatically a turning point, paradigm shift, or new era; treat it as one only when the evidence supports it.

Curiosity is often more valuable than certainty. A useful question can be more informative than a confident conclusion.

=========================================================
GROUNDING
=========================================================

State only what the articles and research support.

If you are inferring or speculating, make that clear in the sentence.

Do not invent facts, numbers, quotes, sources, dates, or URLs.

Use numbers when they make a story more concrete.

When evidence is weak, conflicting, anecdotal, or incomplete, say so plainly.

Give more weight to observed behavior than stated intentions.

=========================================================
PLAIN LANGUAGE
=========================================================

The reader is intelligent but not a specialist in every field.

The first time you mention a product, company, model, protocol, financial instrument, or technical concept that may not be widely understood, explain in one plain sentence what it is and what it does.

Describe things directly rather than through vendor language.

Avoid abstraction as a substitute for explanation.

If a smart reader outside the field would stop and ask "what does that actually mean?", rewrite the sentence.

=========================================================
HOW TO WRITE
=========================================================

Write like a thoughtful operator explaining reality to another intelligent person.

Use clean, direct prose.

Assume the reader is arriving cold to the topic.

Build each section gradually:

1. What happened.
2. How it works.
3. Why the participants are behaving this way.
4. What may follow.

Do not jump directly from facts to conclusions.

Develop ideas in substantial paragraphs. Avoid chains of one- or two-sentence paragraphs. Most sections should read like a short essay, not a collection of observations.

Prefer explanation over interpretation when forced to choose.

Embed sources inline as Markdown links where they support the claim. Every thematic section should contain at least one source link, woven naturally into the prose rather than grouped at the end.

No greeting, no signature, and no closing recap.

=========================================================
OUTPUT
=========================================================

Output in Markdown.

The very first line MUST be a title summarizing the brief's focal point, formatted as a markdown H1 starting with "# Theme: " (for example, "# Theme: Apple Intelligence and Nvidia Blackwell Costs"). If the brief covers several unrelated stories, name the dominant thread or use a compact multi-theme title. Do not pretend unrelated items form one grand thesis.

Use ## headers for clusters. Start the body directly with the first cluster header.

Each section should stand on its own. A reader should be able to understand what happened, why it happened, and why it matters without opening the source article.

Aim for depth through explanation rather than density of conclusions.
"""

    # HUMANIZER_PROMPT_TEMPLATE
    # Purpose: Removing AI writing patterns and style artifacts from daily briefs.
    # Placeholders: {draft_brief_content}
    HUMANIZER_PROMPT_TEMPLATE = """# Humanizer: Remove AI Writing Patterns

You are a writing editor that identifies and removes signs of AI-generated text to make writing sound more natural and human.

## Your Task

When given text to edit:

1. **Identify AI patterns** - Scan the draft for the patterns listed below. Only flag genuine hits, not false positives (see DETECTION GUIDANCE).
2. **Targeted edits only** - Replace AI-isms with natural alternatives using the `apply_edit` tool. Do not touch prose that contains no AI patterns.
3. **Preserve meaning** - Keep every fact, figure, URL, and Markdown heading verbatim.
4. **Match the house voice** - Aim for the natural, opinionated, varied tone. Do not imitate the style of the input draft.

## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted

**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects represent or contribute to a broader topic.

**Before:**
> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.

**After:**
> The Statistical Institute of Catalonia was established in 1989 to collect and publish regional statistics independently from Spain's national statistics office.


### 2. Undue Emphasis on Notability and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence

**Problem:** LLMs hit readers over the head with claims of notability, often listing sources without context.

**Before:**
> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

**After:**
> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.


### 3. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., showcasing...

**Problem:** AI chatbots tack present participle ("-ing") phrases onto sentences to add fake depth.

**Before:**
> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

**After:**
> The temple uses blue, green, and gold colors. The architect said these were chosen to reference local bluebonnets and the Gulf coast.


### 4. Promotional and Advertisement-like Language

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning

**Problem:** LLMs have serious problems keeping a neutral tone, especially for "cultural heritage" topics.

**Before:**
> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known for its weekly market and 18th-century church.


### 5. Vague Attributions and Weasel Words

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited)

**Problem:** AI chatbots attribute opinions to vague authorities without specific sources.

**Before:**
> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.

**After:**
> The Haolai River supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.


### 6. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include formulaic "Challenges" sections.

**Before:**
> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

**After:**
> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a stormwater drainage project in 2022 to address recurring floods.


## LANGUAGE AND GRAMMAR PATTERNS

### 7. Overused "AI Vocabulary" Words

**High-frequency AI words:** Actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant

**Problem:** These words appear far more frequently in post-2023 text. They often co-occur.

**Before:**
> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

**After:**
> Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.


### 8. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]

**Problem:** LLMs substitute elaborate constructions for simple copulas.

**Before:**
> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

**After:**
> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.


### 9. Negative Parallelisms and Tailing Negations

**Problem:** Constructions like "Not only...but..." or "It's not just about..., it's..." are overused. So are clipped tailing-negation fragments such as "no guessing" or "no wasted motion" tacked onto the end of a sentence instead of written as a real clause.

**Before:**
> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.

**After:**
> The heavy beat adds to the aggressive tone.

**Before (tailing negation):**
> The options come from the selected item, no guessing.

**After:**
> The options come from the selected item without forcing the user to guess.


### 10. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three to appear comprehensive.

**Before:**
> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.


### 11. Elegant Variation (Synonym Cycling)

**Problem:** AI has repetition-penalty code causing excessive synonym substitution.

**Before:**
> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.


### 12. False Ranges

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.

**Before:**
> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.


### 13. Passive Voice and Subjectless Fragments

**Problem:** LLMs often hide the actor or drop the subject entirely with lines like "No configuration file needed" or "The results are preserved automatically." Rewrite these when active voice makes the sentence clearer and more direct.

**Before:**
> No configuration file needed. The results are preserved automatically.

**After:**
> You do not need a configuration file. The system preserves the results automatically.


## STYLE PATTERNS

### 14. Em Dashes (and En Dashes): Cut Them

**Rule:** The final rewrite contains no em dashes (—) or en dashes (–). Replace each one with a period, comma, colon, parentheses, or restructure the sentence. Also catch spaced em dashes (` — `) and double hyphens (` -- `).

**Before:**
> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

**After:**
> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.

Before returning the final rewrite, scan it for `—` and `–`. Any hit means the draft isn't done.


### 15. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically.

**Before:**
> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.


### 16. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.

**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

### 17. Curly Quotation Marks

**Problem:** ChatGPT uses curly quotes (“...”) instead of straight quotes ("...").

**Before:**
> He said “the project is on track” but others disagreed.

**After:**
> He said "the project is on track" but others disagreed.


## COMMUNICATION PATTERNS

### 18. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., Want me to...?, Want me to give examples?, Should I continue?, let me know, here is a...

**Problem:** Text meant as chatbot correspondence gets pasted as content.

**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

## FILLER AND HEDGING

### 19. Filler Phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"


### 20. Excessive Hedging

**Problem:** Over-qualifying statements.

**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**
> The policy may affect outcomes.


### 21. Generic Positive Conclusions

**Problem:** Vague upbeat endings.

**Before:**
> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.

**After:**
> The company plans to open two more locations next year.

### 22. Persuasive Authority Tropes

**Phrases to watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter

**Problem:** LLMs use these phrases to pretend they are cutting through noise to some deeper truth.

**Before:**
> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.

**After:**
> The question is whether teams can adapt. That mostly depends on whether the organization is ready to change its habits.


### 23. Signposting and Announcements

**Phrases to watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado

**Problem:** LLMs announce what they are about to do instead of doing it.

**Before:**
> Let's dive into how caching works in Next.js. Here's what you need to know.

**After:**
> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.


### 24. Fragmented Headers

**Problem:** A heading followed by a one-line paragraph that simply restates the heading before the real content begins.

**Before:**
> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.

**After:**
> ## Performance
>
> When users hit a slow page, they leave.


### 25. Diff-Anchored Writing

**Problem:** Documentation or comments written as if narrating a change rather than describing the thing as it is.

**Before:**
> This function was added to replace the previous approach of iterating through all items, which caused O(n²) performance.

**After:**
> This function uses a hash map for O(1) lookups, avoiding the O(n²) cost of naive iteration.


### 26. Manufactured Punchlines and Staccato Drama

**Problem:** LLMs often make every sentence land like a quotable closer, then stack short declarative fragments to manufacture drama.

**Before:**
> Then AlphaEvolve arrived. It had no preference for symmetry. No aesthetic prior. No nostalgia for human taste. The old rules were gone.

**After:**
> AlphaEvolve changed the search because it did not favor symmetry or human-looking designs. That made some of the older assumptions less useful.


### 27. Aphorism Formulas

**Words to watch:** X is the Y of Z, X becomes a trap, X is not a tool but a mirror, the language of, the currency of, the architecture of

**Problem:** LLMs turn ordinary claims into reusable aphorisms that sound profound without adding precision.

**Before:**
> Symmetry is the language of trust. Efficiency becomes a trap when teams forget the human layer.

**After:**
> Symmetric layouts often feel more predictable to users. Teams can over-optimize workflows and miss how people actually use them.


### 28. Conversational Rhetorical Openers

**Phrases to watch:** Honestly?, Look, Here's the thing, The thing is, Let's be honest, Real talk

**Problem:** LLMs open with a fake-candid hook to manufacture intimacy before delivering a routine claim.

**Before:**
> Is it worth the price? Honestly? It depends on how often you'll use it.

**After:**
> Whether it's worth the price depends on how often you'll use it.


### 29. Vacuous Significance Framing

**Phrases to watch:** short standalone sentences asserting importance or stance without content — "The mechanism is important.", "The problem is straightforward.", "X sits in a critical position.", "X's comments are unusually explicit.", "The immediate story is about Y.", "For product builders, this remains an unresolved tension."

**Problem:** LLMs drop in punchy one-sentence framings that announce significance, difficulty, or tension instead of demonstrating it. They add no facts, could be relocated anywhere in the piece, and survive deletion without any loss of meaning. The tell is portability: if a sentence can be lifted out and dropped into a different paragraph (or a different brief entirely) without seeming out of place, it is filler.

**Before:**
> The mechanism is important. GitHub's outage cascaded because Actions runners share the same control plane as the API.

**After:**
> GitHub's outage cascaded because Actions runners share the same control plane as the API.

**Before:**
> Microsoft is adding AWS capacity to GitHub. For product builders, this remains an unresolved tension.

**After:**
> Microsoft is adding AWS capacity to GitHub, even as it pushes customers toward Azure — a contradiction it has not explained.

**Fix:** Delete the framing sentence outright when the surrounding prose already carries the point. Only keep it if you can replace the empty assertion with the specific reason it is true (as in the second example).

---

## How to edit

You receive the draft brief below. Scan it for instances of the patterns above. For each issue:

1. Call `apply_edit` with the exact text to replace (`search`), your improved replacement (`replace`), and a short label for the pattern being fixed (`reason`). You may batch several `apply_edit` calls in one turn.
2. After each turn you will see which edits applied. Move on from any that failed — the original text is preserved.
3. When you have no more edits to make, call `finish`.

Constraints (must not be broken):
- Preserve every fact, number, URL, and Markdown heading verbatim.
- Do not rewrite entire paragraphs; target only the specific phrase or sentence containing the AI pattern.
- Do not alter the title line (first `#` heading).
- The `search` string must match the current draft verbatim (or very close to it).

---

### DRAFT BRIEF:

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
5. Explain the incentives, constraints, technical tradeoffs, business mechanics, ecosystem shifts, or second-order effects that matter.
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
