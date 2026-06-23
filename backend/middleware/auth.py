"""Authentication middleware using backend-owned Flask sessions."""
from __future__ import annotations

import logging
from functools import wraps
from types import SimpleNamespace

from flask import g, jsonify, request, session

from database import get_user_by_id, upsert_user
from config import Config

logger = logging.getLogger(__name__)

def _dev_bypass_auth_enabled() -> bool:
    return (
        Config.APP_ENV.lower() != "test"
        and Config.DEV_BYPASS_AUTH
    )


def dev_bypass_user():
    """Return the local dev bypass user.

    The account is configured via DEV_BYPASS_EMAIL / DEV_BYPASS_NAME in your
    local (gitignored) .env. Falls back to a generic dev user if unset.
    """
    email = Config.DEV_BYPASS_EMAIL
    full_name = Config.DEV_BYPASS_NAME
    return upsert_user(email, full_name=full_name)


def _as_user_object(user: dict):
    return SimpleNamespace(**user)


def _load_session_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def _load_test_user():
    """Allow existing tests and local harnesses to pass a bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if Config.APP_ENV.lower() == "test" and auth_header.startswith("Bearer "):
        return upsert_user(
            "test@example.com",
            full_name="Test User",
            avatar_url=None,
        )
    return None


def require_auth(f):
    """Decorator to require a local authenticated user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if _dev_bypass_auth_enabled():
            user = dev_bypass_user()
        else:
            user = _load_session_user() or _load_test_user()

        if not user:
            return jsonify({"error": "Authentication required"}), 401

        g.user = _as_user_object(user)
        return f(*args, **kwargs)

    return decorated_function


def current_user_optional():
    """Attach g.user when a valid session/test token exists, otherwise None."""
    user = _load_session_user() or _load_test_user()
    g.user = _as_user_object(user) if user else None
    return g.user
