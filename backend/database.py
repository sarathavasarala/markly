"""Supabase client initialization."""
from supabase import create_client, Client
from config import Config


_supabase_client: Client | None = None


def get_supabase() -> Client:
    """Get or create Supabase client singleton."""
    global _supabase_client
    
    if _supabase_client is None:
        if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
            raise ValueError("Supabase configuration is missing")
        
        _supabase_client = create_client(
            Config.SUPABASE_URL,
            Config.SUPABASE_SERVICE_KEY
        )
    
    return _supabase_client
