"""Authentication middleware using Supabase Auth."""
import os
import logging
from functools import wraps
from flask import request, jsonify, g

from database import get_supabase, get_auth_client

logger = logging.getLogger(__name__)

# Auth bypass off by default; enable via env only if intentionally set
DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"


def require_auth(f):
    """Decorator to require authentication for a route via Supabase JWT."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bypass auth in dev mode (ONLY if explicitly enabled)
        if DEV_BYPASS_AUTH:
            # Mock a superuser client if bypassing
            # Note: RLS might block this unless we use service role, 
            # so strict RLS testing requires disabling bypass
            g.user = {"id": "dev-user", "email": "dev@local"}
            g.supabase = get_supabase() # Service role
            return f(*args, **kwargs)
        
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        if not token:
            return jsonify({"error": "Missing authentication token"}), 401
        
        try:
            # Use the service role client to verify the user's JWT
            # The get_user(jwt) method validates the token and returns user info
            admin_client = get_supabase()
            user_response = admin_client.auth.get_user(token)
            
            if not user_response or not user_response.user:
                return jsonify({"error": "Invalid or expired token"}), 401
            
            # Create a client scoped to this user for subsequent DB operations
            # This client will include the user's JWT in requests for RLS
            client = get_auth_client(token)
                 
            # Store in context
            g.user = user_response.user
            g.supabase = client  # Use this client for all DB calls in the route!
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({"error": "Invalid authentication credentials"}), 401
    
    return decorated_function
