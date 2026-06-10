"""Backend-owned authentication routes."""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, jsonify, redirect, request, session, url_for

from config import Config
from database import is_email_allowed, upsert_user
from middleware.auth import current_user_optional, require_auth


auth_bp = Blueprint("auth", __name__)


def _redirect_base_url() -> str:
    configured = Config.OAUTH_REDIRECT_BASE_URL
    if configured:
        return configured.rstrip("/")
    return request.host_url.rstrip("/")


def _callback_url() -> str:
    return f"{_redirect_base_url()}{url_for('auth.google_callback')}"


@auth_bp.route("/me", methods=["GET"])
def me():
    from middleware.auth import _dev_bypass_auth_enabled, dev_bypass_user
    if _dev_bypass_auth_enabled():
        user = dev_bypass_user()
        return jsonify({
            "user": {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "user_metadata": {
                    "full_name": user["full_name"],
                    "name": user["full_name"],
                    "avatar_url": user["avatar_url"],
                    "picture": user["avatar_url"],
                },
            },
            "is_authenticated": True,
        })

    user = current_user_optional()
    if not user:
        return jsonify({"user": None, "is_authenticated": False})
    return jsonify({
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "user_metadata": {
                "full_name": user.full_name,
                "name": user.full_name,
                "avatar_url": user.avatar_url,
                "picture": user.avatar_url,
            },
        },
        "is_authenticated": True,
    })


@auth_bp.route("/google/login", methods=["GET"])
def google_login():
    from middleware.auth import _dev_bypass_auth_enabled, dev_bypass_user
    if _dev_bypass_auth_enabled():
        user = dev_bypass_user()
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        return redirect("/")

    if not Config.GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google OAuth is not configured"}), 500

    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": _callback_url(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@auth_bp.route("/google/callback", methods=["GET"])
def google_callback():
    expected_state = session.pop("oauth_state", None)
    if not expected_state or request.args.get("state") != expected_state:
        return jsonify({"error": "Invalid OAuth state"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing OAuth code"}), 400
    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        return jsonify({"error": "Google OAuth is not configured"}), 500

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": _callback_url(),
        },
        timeout=15,
    )
    if not token_response.ok:
        return jsonify({"error": "Failed to exchange OAuth code"}), 401

    access_token = token_response.json().get("access_token")
    if not access_token:
        return jsonify({"error": "Google OAuth did not return an access token"}), 401

    userinfo_response = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not userinfo_response.ok:
        return jsonify({"error": "Failed to load Google profile"}), 401

    profile = userinfo_response.json()
    email = (profile.get("email") or "").lower().strip()
    if not email:
        return jsonify({"error": "Google profile did not include an email"}), 401
    if not is_email_allowed(email):
        return jsonify({"error": "This email is not allowed to use markly"}), 403

    user = upsert_user(
        email,
        full_name=profile.get("name"),
        avatar_url=profile.get("picture"),
    )
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    return redirect("/")


@auth_bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    session.clear()
    return jsonify({"success": True})
