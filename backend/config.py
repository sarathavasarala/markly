"""Application configuration."""
import os
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.abspath(__file__))
env = os.getenv("APP_ENV", "prod")
env_file = os.path.join(base_dir, f".env.{env}")

if os.path.exists(env_file):
    load_dotenv(env_file, override=True)
else:
    load_dotenv(os.path.join(base_dir, ".env"), override=True)


class Config:
    """Base configuration."""
    
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    # SQLite database owned by the backend
    MARKLY_DB_PATH = os.getenv(
        "MARKLY_DB_PATH",
        os.path.join(base_dir, "markly.db")
    )
    SQLITE_JOURNAL_MODE = os.getenv("SQLITE_JOURNAL_MODE", "DELETE")
    
    # Auth
    ALLOWED_EMAILS = os.getenv("ALLOWED_EMAILS", "")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    OAUTH_REDIRECT_BASE_URL = os.getenv("OAUTH_REDIRECT_BASE_URL")
    
    # Feature flags
    ENABLE_EMBEDDINGS = os.getenv("ENABLE_EMBEDDINGS", "true").lower() == "true"
    ENABLE_SEMANTIC_SEARCH = os.getenv("ENABLE_SEMANTIC_SEARCH", "false").lower() == "true"
    
    # Azure OpenAI (all must come from environment)
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    # Cheaper model for bulk/batch operations (e.g., imports)
    AZURE_OPENAI_NANO_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_NANO_DEPLOYMENT_NAME")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    # Embeddings can require a different API version than chat/completions
    AZURE_OPENAI_EMBEDDING_API_VERSION = os.getenv(
        "AZURE_OPENAI_EMBEDDING_API_VERSION", "2024-12-01-preview"
    )
    
    # Custom LLM overrides specifically for Signal daily brief generation
    SIGNAL_AZURE_OPENAI_API_KEY = os.getenv("SIGNAL_AZURE_OPENAI_API_KEY")
    SIGNAL_AZURE_OPENAI_ENDPOINT = os.getenv("SIGNAL_AZURE_OPENAI_ENDPOINT")
    SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("SIGNAL_AZURE_OPENAI_DEPLOYMENT_NAME")
    SIGNAL_AZURE_OPENAI_API_VERSION = os.getenv("SIGNAL_AZURE_OPENAI_API_VERSION")
    
    SESSION_EXPIRY_DAYS = 365  # 1 year

    # Archive settings
    ARCHIVE_MAX_CHARS = int(os.getenv("ARCHIVE_MAX_CHARS", "200000"))
    ARCHIVE_BACKFILL_BATCH_SIZE = int(os.getenv("ARCHIVE_BACKFILL_BATCH_SIZE", "10"))

    # Feed Radar settings
    FEED_RADAR_ITEMS_PER_SOURCE = int(os.getenv("FEED_RADAR_ITEMS_PER_SOURCE", "100"))
    FEED_MAX_FAILURES = int(os.getenv("FEED_MAX_FAILURES", "10"))
    FEED_BACKOFF_BASE_MINUTES = int(os.getenv("FEED_BACKOFF_BASE_MINUTES", "30"))
    FEED_BACKOFF_MAX_MINUTES = int(os.getenv("FEED_BACKOFF_MAX_MINUTES", "1440"))

    # Signal settings
    SIGNAL_CANDIDATE_LIMIT = int(os.getenv("SIGNAL_CANDIDATE_LIMIT", "75"))
    # Embedding-based candidate selection knobs (gentle defaults that preserve
    # current behavior at small scale).
    SIGNAL_RECENCY_HALF_LIFE_DAYS = float(os.getenv("SIGNAL_RECENCY_HALF_LIFE_DAYS", "3"))
    # Recent candidate pool is pulled at this multiple of the candidate limit
    # before ranking. Embedding ranking only kicks in when the pool actually
    # exceeds the candidate limit.
    SIGNAL_CANDIDATE_POOL_MULTIPLIER = int(os.getenv("SIGNAL_CANDIDATE_POOL_MULTIPLIER", "3"))
    # Items briefed within this window are excluded from new briefs (anti-repeat).
    SIGNAL_BRIEFED_EXCLUDE_DAYS = float(os.getenv("SIGNAL_BRIEFED_EXCLUDE_DAYS", "7"))
    # Only rank by embeddings when at least this fraction of the pool is embedded;
    # otherwise fall back to recency order (and skip the taste-profile embedding call).
    SIGNAL_EMBED_MIN_COVERAGE = float(os.getenv("SIGNAL_EMBED_MIN_COVERAGE", "0.5"))
    # Named magic numbers (defaults match prior hardcoded values).
    SIGNAL_MAX_SYNTHESIS_ARTICLES = int(os.getenv("SIGNAL_MAX_SYNTHESIS_ARTICLES", "15"))
    SIGNAL_CONTENT_MAX_CHARS = int(os.getenv("SIGNAL_CONTENT_MAX_CHARS", "8000"))
    SIGNAL_CONTENT_HEAD_CHARS = int(os.getenv("SIGNAL_CONTENT_HEAD_CHARS", "6500"))
    SIGNAL_CONTENT_TAIL_CHARS = int(os.getenv("SIGNAL_CONTENT_TAIL_CHARS", "1500"))
    # Per-refresh cap on how many backlog items get embedded, so a large backlog
    # smooths across multiple refreshes instead of bursting hundreds of calls at once.
    SIGNAL_EMBED_MAX_PER_RUN = int(os.getenv("SIGNAL_EMBED_MAX_PER_RUN", "200"))

    # Optional services
    JINA_READER_API_KEY = os.getenv("JINA_READER_API_KEY")
    PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY")

    
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
