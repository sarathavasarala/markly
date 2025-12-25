"""Authentication routes."""
import secrets
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify

from config import Config
from database import get_supabase

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login with secret phrase."""
    logger.info("=== LOGIN ATTEMPT ===")
    
    data = request.get_json()
    logger.debug(f"Request data: {data}")
    
    if not data or "secret_phrase" not in data:
        logger.warning("No secret_phrase in request")
        return jsonify({"error": "Secret phrase is required"}), 400
    
    secret_phrase = (data.get("secret_phrase") or "").strip()
    expected_phrase = (Config.AUTH_SECRET_PHRASE or "").strip()

    logger.debug("Received phrase (sanitized, lowercased for comparison)")
    logger.debug(f"Expected phrase configured: {'SET' if expected_phrase else 'MISSING'}")
    
    # Validate against configured secret phrase (case-insensitive)
    if not expected_phrase:
        logger.error("AUTH_SECRET_PHRASE is not configured")
        return jsonify({"error": "Auth not configured"}), 500
    
    if secret_phrase.lower() != expected_phrase.lower():
        logger.warning("Invalid secret phrase - no match")
        return jsonify({"error": "Invalid secret phrase"}), 401
    
    logger.info("Secret phrase matched!")
    
    # Generate session token
    session_token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=Config.SESSION_EXPIRY_DAYS)
    
    try:
        logger.debug("Connecting to Supabase...")
        supabase = get_supabase()
        
        # Create session in database
        session_data = {
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
        }
        
        logger.debug(f"Inserting session: {session_data}")
        result = supabase.table("sessions").insert(session_data).execute()
        logger.debug(f"Supabase result: {result}")
        
        logger.info("Login successful!")
        return jsonify({
            "token": session_token,
            "expires_at": expires_at.isoformat(),
        })
        
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to create session: {str(e)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout and invalidate session."""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return jsonify({"message": "Already logged out"}), 200
    
    token = auth_header[7:]
    
    if not token:
        return jsonify({"message": "Already logged out"}), 200
    
    try:
        supabase = get_supabase()
        supabase.table("sessions").delete().eq("session_token", token).execute()
        
        return jsonify({"message": "Logged out successfully"})
        
    except Exception as e:
        # Even if deletion fails, consider logout successful
        return jsonify({"message": "Logged out"})


@auth_bp.route("/verify", methods=["GET"])
def verify():
    """Verify if current session is valid."""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        return jsonify({"valid": False}), 401
    
    token = auth_header[7:]
    
    if not token:
        return jsonify({"valid": False}), 401
    
    try:
        supabase = get_supabase()
        result = supabase.table("sessions").select("expires_at").eq(
            "session_token", token
        ).single().execute()
        
        if not result.data:
            return jsonify({"valid": False}), 401
        
        expires_at = datetime.fromisoformat(result.data["expires_at"].replace("Z", "+00:00"))
        
        if expires_at < datetime.now(timezone.utc):
            return jsonify({"valid": False, "reason": "expired"}), 401
        
        return jsonify({
            "valid": True,
            "expires_at": expires_at.isoformat()
        })
        
    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 401
