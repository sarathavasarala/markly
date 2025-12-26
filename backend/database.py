"""Supabase client initialization."""
from supabase import create_client, Client, ClientOptions
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


def get_auth_client(token: str) -> Client:
    """Get a Supabase client acting as the authenticated user.
    
    This client will trigger RLS policies in the database effectively.
    """
    if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
        raise ValueError("Supabase configuration is missing")
    
    # Use the proper ClientOptions from supabase library with custom headers
    options = ClientOptions(
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # We use the anon key or service key for initialization, but the Authorization header 
    # overrides it for RLS purposes when making requests.
    client = create_client(
        Config.SUPABASE_URL,
        Config.SUPABASE_SERVICE_KEY,
        options=options
    )
    
    return client
