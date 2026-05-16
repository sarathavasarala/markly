"""Folder routes."""
from __future__ import annotations

import logging
import sqlite3

from flask import Blueprint, g, jsonify, request

from database import get_db, new_id, row_to_dict, rows_to_dicts, utc_now
from middleware.auth import require_auth

logger = logging.getLogger(__name__)
folders_bp = Blueprint("folders", __name__)


@folders_bp.route("", methods=["GET"])
@require_auth
def list_folders():
    """List all folders for the current user with bookmark counts."""
    try:
        rows = get_db().execute(
            """
            SELECT f.*, COUNT(b.id) AS bookmark_count
            FROM folders f
            LEFT JOIN bookmarks b ON b.folder_id = f.id AND b.user_id = f.user_id
            WHERE f.user_id = ?
            GROUP BY f.id
            ORDER BY f.name
            """,
            (g.user.id,),
        ).fetchall()
        return jsonify(rows_to_dicts(rows))
    except Exception as e:
        logger.error(f"Failed to list folders: {str(e)}")
        return jsonify({"error": f"Failed to list folders: {str(e)}"}), 500


@folders_bp.route("", methods=["POST"])
@require_auth
def create_folder():
    """Create a new folder."""
    data = request.get_json()
    if not data or "name" not in data:
        return jsonify({"error": "Folder name is required"}), 400

    conn = get_db()
    now = utc_now()
    folder_id = new_id()
    try:
        conn.execute(
            """
            INSERT INTO folders (id, user_id, name, icon, color, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder_id,
                g.user.id,
                data["name"].strip(),
                data.get("icon"),
                data.get("color"),
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except sqlite3.IntegrityError as e:
        conn.rollback()
        logger.error(f"Failed to create folder: {str(e)}")
        if "UNIQUE" in str(e).upper():
            return jsonify({"error": "A folder with this name already exists"}), 409
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to create folder: {str(e)}")
        return jsonify({"error": str(e)}), 500


@folders_bp.route("/<folder_id>", methods=["PATCH"])
@require_auth
def update_folder(folder_id: str):
    """Update folder metadata."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed_fields = ["name", "icon", "color"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    update_data["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in update_data)
    conn = get_db()
    try:
        conn.execute(
            f"UPDATE folders SET {assignments} WHERE id = ? AND user_id = ?",
            tuple(update_data.values()) + (folder_id, g.user.id),
        )
        row = conn.execute(
            "SELECT * FROM folders WHERE id = ? AND user_id = ?",
            (folder_id, g.user.id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Folder not found"}), 404
        conn.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to update folder: {str(e)}")
        return jsonify({"error": str(e)}), 500


@folders_bp.route("/<folder_id>", methods=["DELETE"])
@require_auth
def delete_folder(folder_id: str):
    """Delete a folder and leave its bookmarks unfiled."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM folders WHERE id = ? AND user_id = ?",
            (folder_id, g.user.id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Folder not found"}), 404
        conn.execute("DELETE FROM folders WHERE id = ? AND user_id = ?", (folder_id, g.user.id))
        conn.commit()
        return jsonify({"message": "Folder deleted successfully"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to delete folder: {str(e)}")
        return jsonify({"error": str(e)}), 500
