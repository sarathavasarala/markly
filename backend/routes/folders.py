"""Folder routes."""
import logging
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth

logger = logging.getLogger(__name__)
folders_bp = Blueprint("folders", __name__)

@folders_bp.route("", methods=["GET"])
@require_auth
def list_folders():
    """List all folders for the current user with bookmark counts."""
    try:
        supabase = g.supabase
        # Get folders
        result = supabase.table("folders").select("*").eq("user_id", g.user.id).order("name").execute()
        folders = result.data or []

        # Get bookmark counts per folder
        if folders:
            folder_ids = [f["id"] for f in folders]
            count_map = {}
            for folder_id in folder_ids:
                count_result = supabase.table("bookmarks").select(
                    "id", count="exact"
                ).eq("user_id", g.user.id).eq("folder_id", folder_id).execute()
                count_map[folder_id] = count_result.count or 0

            # Merge counts into folder objects
            for folder in folders:
                folder["bookmark_count"] = count_map.get(folder["id"], 0)

        return jsonify(folders)
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
    
    try:
        supabase = g.supabase
        folder_data = {
            "name": data["name"].strip(),
            "icon": data.get("icon"),
            "color": data.get("color"),
            "user_id": g.user.id
        }
        
        result = supabase.table("folders").insert(folder_data).execute()
        if not result.data:
            return jsonify({"error": "Failed to create folder"}), 500
            
        return jsonify(result.data[0]), 201
    except Exception as e:
        logger.error(f"Failed to create folder: {str(e)}")
        if "duplicate key" in str(e).lower():
            return jsonify({"error": "A folder with this name already exists"}), 409
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
        
    try:
        supabase = g.supabase
        result = supabase.table("folders").update(update_data).eq("id", folder_id).eq("user_id", g.user.id).execute()
        
        if not result.data:
            return jsonify({"error": "Folder not found"}), 404
            
        return jsonify(result.data[0])
    except Exception as e:
        logger.error(f"Failed to update folder: {str(e)}")
        return jsonify({"error": str(e)}), 500

@folders_bp.route("/<folder_id>", methods=["DELETE"])
@require_auth
def delete_folder(folder_id: str):
    """Delete a folder. Associated bookmarks will have folder_id set to NULL due to ON DELETE SET NULL."""
    try:
        supabase = g.supabase
        result = supabase.table("folders").delete().eq("id", folder_id).eq("user_id", g.user.id).execute()
        
        if not result.data:
            return jsonify({"error": "Folder not found"}), 404
            
        return jsonify({"message": "Folder deleted successfully"})
    except Exception as e:
        logger.error(f"Failed to delete folder: {str(e)}")
        return jsonify({"error": str(e)}), 500
