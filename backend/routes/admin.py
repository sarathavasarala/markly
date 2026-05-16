"""Temporary admin operations for deployment maintenance."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from config import Config

admin_bp = Blueprint("admin", __name__)


def _authorized() -> bool:
    token = Config.MIGRATION_ADMIN_TOKEN
    provided = request.headers.get("X-Migration-Token", "")
    return bool(token and provided and provided == token)


@admin_bp.route("/migrate-supabase", methods=["POST"])
def migrate_supabase():
    """Run the one-time Supabase-to-SQLite migration without container SSH."""
    if not _authorized():
        return jsonify({"error": "Unauthorized"}), 401

    from scripts.migrate_supabase_to_sqlite import migrate

    result = migrate()
    return jsonify({"success": True, **result})
