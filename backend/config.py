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
    
    SESSION_EXPIRY_DAYS = 365  # 1 year

    # Archive settings
    ARCHIVE_MAX_CHARS = int(os.getenv("ARCHIVE_MAX_CHARS", "200000"))
    ARCHIVE_BACKFILL_BATCH_SIZE = int(os.getenv("ARCHIVE_BACKFILL_BATCH_SIZE", "10"))

    # Optional services
    JINA_READER_API_KEY = os.getenv("JINA_READER_API_KEY")
    
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
