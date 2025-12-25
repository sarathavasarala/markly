"""Authentication middleware with caching."""
import os
import time
import logging
from functools import wraps
from threading import Lock
from flask import request, jsonify
from datetime import datetime, timezone

from database import get_supabase

logger = logging.getLogger(__name__)

# Auth bypass off by default; enable via env only if intentionally set
DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"

# Token cache with TTL (reduces DB load)
_token_cache = {}  # token -> (expires_at, cached_time)
_cache_lock = Lock()
CACHE_TTL_SECONDS = 300  # 5 minutes


def _get_cached_session(token: str):
    """Get session from cache if valid."""
    with _cache_lock:
        if token in _token_cache:
            expires_at, cached_time = _token_cache[token]
            # Check if cache entry is still fresh
            if time.time() - cached_time < CACHE_TTL_SECONDS:
                return expires_at
            # Cache expired, remove it
            del _token_cache[token]
    return None


def _cache_session(token: str, expires_at: datetime):
    """Cache a valid session."""
    with _cache_lock:
        _token_cache[token] = (expires_at, time.time())
        # Prune cache if too large (simple LRU-like behavior)
        if len(_token_cache) > 1000:
            # Remove oldest entries
            sorted_items = sorted(_token_cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_items[:200]:
                del _token_cache[key]


def invalidate_session_cache(token: str):
    """Invalidate a cached session (call on logout)."""
    with _cache_lock:
        _token_cache.pop(token, None)


def require_auth(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bypass auth in dev mode
        if DEV_BYPASS_AUTH:
            return f(*args, **kwargs)
        
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        if not token:
            return jsonify({"error": "Missing authentication token"}), 401
        
        # Check cache first
        cached_expires = _get_cached_session(token)
        if cached_expires:
            if cached_expires > datetime.now(timezone.utc):
                return f(*args, **kwargs)
            else:
                invalidate_session_cache(token)
                return jsonify({"error": "Session expired"}), 401
        
        # Validate token against database
        try:
            supabase = get_supabase()
            result = supabase.table("sessions").select("*").eq(
                "session_token", token
            ).single().execute()
            
            if not result.data:
                return jsonify({"error": "Invalid session token"}), 401
            
            session = result.data
            expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
            
            if expires_at < datetime.now(timezone.utc):
                # Clean up expired session
                supabase.table("sessions").delete().eq("session_token", token).execute()
                return jsonify({"error": "Session expired"}), 401
            
            # Cache the valid session
            _cache_session(token, expires_at)
            
            # Token is valid, continue to route
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({"error": f"Authentication error: {str(e)}"}), 401
    
    return decorated_function
