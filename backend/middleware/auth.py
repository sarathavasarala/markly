"""Authentication middleware using backend-owned Flask sessions."""
from __future__ import annotations

import logging
import os
from functools import wraps
from types import SimpleNamespace

from flask import g, jsonify, request, session

from database import get_user_by_id, upsert_user

logger = logging.getLogger(__name__)

DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "false").lower() == "true"


def _as_user_object(user: dict):
    return SimpleNamespace(**user)


def _load_session_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def _load_test_user():
    """Allow existing tests and local harnesses to pass a bearer token."""
    app_env = os.getenv("APP_ENV", "").lower()
    auth_header = request.headers.get("Authorization", "")
    if app_env == "test" and auth_header.startswith("Bearer "):
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
        if DEV_BYPASS_AUTH:
            user = upsert_user("dev@local", full_name="Development User")
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
