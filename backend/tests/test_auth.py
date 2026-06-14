"""Tests for auth routes and email allowlist enforcement."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_token_resp(ok=True, access_token="fake-token"):
    m = MagicMock()
    m.ok = ok
    m.json.return_value = {"access_token": access_token} if ok else {}
    return m


def _make_userinfo_resp(ok=True, email="user@example.com", name="User"):
    m = MagicMock()
    m.ok = ok
    m.json.return_value = {"email": email, "name": name, "picture": None} if ok else {}
    return m


def _seed_state(client, state="test-state"):
    with client.session_transaction() as sess:
        sess["oauth_state"] = state
    return state


# ── allowlist unit tests ──────────────────────────────────────────────────────

def test_allowed_emails_parses_csv(monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "Alice@Example.com, BOB@EXAMPLE.COM , ")
    from database import allowed_emails
    assert allowed_emails() == {"alice@example.com", "bob@example.com"}


def test_allowed_emails_empty_returns_empty_set(monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "")
    from database import allowed_emails
    assert allowed_emails() == set()


def test_is_email_allowed_match(monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "alice@example.com")
    from database import is_email_allowed
    assert is_email_allowed("alice@example.com") is True
    assert is_email_allowed("ALICE@EXAMPLE.COM") is True  # case-insensitive


def test_is_email_allowed_no_match(monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "alice@example.com")
    from database import is_email_allowed
    assert is_email_allowed("other@example.com") is False


def test_is_email_allowed_empty_list_denies_all(monkeypatch):
    """Empty ALLOWED_EMAILS must deny everyone (fail-closed)."""
    import config
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "")
    from database import is_email_allowed
    assert is_email_allowed("anyone@example.com") is False


# ── OAuth callback tests ──────────────────────────────────────────────────────

def test_callback_allowed_email_creates_session(client, monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "allowed@example.com")

    state = _seed_state(client)
    with patch("routes.auth.requests.post", return_value=_make_token_resp()), \
         patch("routes.auth.requests.get", return_value=_make_userinfo_resp(email="allowed@example.com")):
        resp = client.get(f"/api/auth/google/callback?code=abc&state={state}")

    assert resp.status_code == 302
    assert resp.headers["Location"] in ("/", "http://localhost/")
    with client.session_transaction() as sess:
        assert "user_id" in sess


def test_callback_denied_email_redirects_to_login(client, monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "allowed@example.com")

    state = _seed_state(client)
    with patch("routes.auth.requests.post", return_value=_make_token_resp()), \
         patch("routes.auth.requests.get", return_value=_make_userinfo_resp(email="notallowed@example.com")):
        resp = client.get(f"/api/auth/google/callback?code=abc&state={state}")

    assert resp.status_code == 302
    assert "not_available" in resp.headers["Location"]
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_callback_empty_allowlist_denies_all(client, monkeypatch):
    import config
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config.Config, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(config.Config, "ALLOWED_EMAILS", "")

    state = _seed_state(client)
    with patch("routes.auth.requests.post", return_value=_make_token_resp()), \
         patch("routes.auth.requests.get", return_value=_make_userinfo_resp(email="anyone@example.com")):
        resp = client.get(f"/api/auth/google/callback?code=abc&state={state}")

    assert resp.status_code == 302
    assert "not_available" in resp.headers["Location"]


def test_callback_invalid_state_returns_400(client):
    _seed_state(client, "correct-state")
    resp = client.get("/api/auth/google/callback?code=abc&state=wrong-state")
    assert resp.status_code == 400


def test_callback_missing_code_returns_400(client):
    state = _seed_state(client)
    resp = client.get(f"/api/auth/google/callback?state={state}")
    assert resp.status_code == 400


def test_me_unauthenticated_returns_not_authenticated(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_authenticated"] is False
    assert data["user"] is None


# ── dev bypass safeguard ──────────────────────────────────────────────────────

def test_dev_bypass_disabled_in_test_env():
    """DEV_BYPASS_AUTH must never activate when APP_ENV=test."""
    assert os.getenv("APP_ENV") == "test"
    from middleware.auth import _dev_bypass_auth_enabled
    assert _dev_bypass_auth_enabled() is False
