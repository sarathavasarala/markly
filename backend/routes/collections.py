"""Collections routes."""
from flask import Blueprint, request, jsonify

from database import get_supabase
from middleware.auth import require_auth
from services.openai_service import AzureOpenAIService

collections_bp = Blueprint("collections", __name__)


@collections_bp.route("", methods=["GET"])
@require_auth
def list_collections():
    """List all collections with bookmark counts."""
    try:
        supabase = get_supabase()
        
        # Use optimized view that includes bookmark counts (fixes N+1 query)
        result = supabase.table("collection_details").select("*").order(
            "updated_at", desc=True
        ).execute()
        
        return jsonify({"collections": result.data})
        
    except Exception as e:
        return jsonify({"error": f"Failed to list collections: {str(e)}"}), 500


@collections_bp.route("", methods=["POST"])
@require_auth
def create_collection():
    """Create a new collection."""
    data = request.get_json()
    
    if not data or "name" not in data:
        return jsonify({"error": "Collection name is required"}), 400
    
    collection_data = {
        "name": data["name"].strip(),
        "description": data.get("description", "").strip() or None,
        "icon": data.get("icon", "📁"),
        "color": data.get("color", "#6366f1"),
    }
    
    try:
        supabase = get_supabase()
        
        result = supabase.table("collections").insert(collection_data).execute()
        
        if not result.data:
            return jsonify({"error": "Failed to create collection"}), 500
        
        collection = result.data[0]
        collection["bookmark_count"] = 0
        
        return jsonify(collection), 201
        
    except Exception as e:
        return jsonify({"error": f"Failed to create collection: {str(e)}"}), 500


@collections_bp.route("/<collection_id>", methods=["GET"])
@require_auth
def get_collection(collection_id: str):
    """Get a collection with its bookmarks."""
    try:
        supabase = get_supabase()
        
        # Get collection
        result = supabase.table("collections").select("*").eq(
            "id", collection_id
        ).single().execute()
        
        if not result.data:
            return jsonify({"error": "Collection not found"}), 404
        
        collection = result.data
        
        # Get bookmarks in this collection
        bc_result = supabase.table("bookmark_collections").select(
            "bookmark_id, added_at"
        ).eq("collection_id", collection_id).order("added_at", desc=True).execute()
        
        bookmark_ids = [bc["bookmark_id"] for bc in bc_result.data]
        
        if bookmark_ids:
            bookmarks_result = supabase.table("bookmarks").select(
                "id, url, domain, clean_title, ai_summary, auto_tags, "
                "favicon_url, thumbnail_url, content_type, created_at"
            ).in_("id", bookmark_ids).execute()
            
            collection["bookmarks"] = bookmarks_result.data
        else:
            collection["bookmarks"] = []
        
        collection["bookmark_count"] = len(collection["bookmarks"])
        
        return jsonify(collection)
        
    except Exception as e:
        if "PGRST116" in str(e):
            return jsonify({"error": "Collection not found"}), 404
        return jsonify({"error": f"Failed to get collection: {str(e)}"}), 500


@collections_bp.route("/<collection_id>", methods=["PUT"])
@require_auth
def update_collection(collection_id: str):
    """Update a collection's metadata."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Allowed fields to update
    allowed_fields = ["name", "description", "icon", "color"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400
    
    try:
        supabase = get_supabase()
        
        result = supabase.table("collections").update(update_data).eq(
            "id", collection_id
        ).execute()
        
        if not result.data:
            return jsonify({"error": "Collection not found"}), 404
        
        return jsonify(result.data[0])
        
    except Exception as e:
        return jsonify({"error": f"Failed to update collection: {str(e)}"}), 500


@collections_bp.route("/<collection_id>", methods=["DELETE"])
@require_auth
def delete_collection(collection_id: str):
    """Delete a collection."""
    try:
        supabase = get_supabase()
        
        result = supabase.table("collections").delete().eq(
            "id", collection_id
        ).execute()
        
        if not result.data:
            return jsonify({"error": "Collection not found"}), 404
        
        return jsonify({"message": "Collection deleted successfully"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to delete collection: {str(e)}"}), 500


@collections_bp.route("/<collection_id>/bookmarks/<bookmark_id>", methods=["DELETE"])
@require_auth
def remove_bookmark_from_collection(collection_id: str, bookmark_id: str):
    """Remove a bookmark from a collection."""
    try:
        supabase = get_supabase()
        
        supabase.table("bookmark_collections").delete().eq(
            "collection_id", collection_id
        ).eq("bookmark_id", bookmark_id).execute()
        
        return jsonify({"message": "Bookmark removed from collection"})
        
    except Exception as e:
        return jsonify({"error": f"Failed to remove bookmark: {str(e)}"}), 500


@collections_bp.route("/generate", methods=["POST"])
@require_auth
def generate_collections():
    """Generate collection proposals using AI."""
    try:
        supabase = get_supabase()
        
        # Get all completed bookmarks
        result = supabase.table("bookmarks").select(
            "id, url, domain, clean_title, original_title, ai_summary, "
            "auto_tags, content_type, intent_type"
        ).eq("enrichment_status", "completed").execute()
        
        bookmarks = result.data
        
        if len(bookmarks) < 5:
            return jsonify({
                "error": "Need at least 5 bookmarks to generate collections",
                "proposals": []
            }), 400
        
        # Generate proposals using LLM
        proposals = AzureOpenAIService.generate_collection_proposals(bookmarks)
        
        # Validate bookmark IDs in proposals
        valid_ids = {b["id"] for b in bookmarks}
        for proposal in proposals:
            proposal["bookmark_ids"] = [
                bid for bid in proposal.get("bookmark_ids", [])
                if bid in valid_ids
            ]
            proposal["bookmark_count"] = len(proposal["bookmark_ids"])
        
        # Filter out empty proposals
        proposals = [p for p in proposals if p["bookmark_count"] > 0]
        
        return jsonify({"proposals": proposals})
        
    except Exception as e:
        return jsonify({"error": f"Failed to generate collections: {str(e)}"}), 500


@collections_bp.route("/accept", methods=["POST"])
@require_auth
def accept_collection_proposals():
    """Accept and create collections from proposals."""
    data = request.get_json()
    
    if not data or "proposals" not in data:
        return jsonify({"error": "Proposals are required"}), 400
    
    proposals = data["proposals"]
    
    if not proposals:
        return jsonify({"error": "No proposals provided"}), 400
    
    try:
        supabase = get_supabase()
        created_collections = []
        
        for proposal in proposals:
            # Create collection
            collection_data = {
                "name": proposal.get("name", "Untitled"),
                "description": proposal.get("description"),
                "icon": proposal.get("suggested_icon", "📁"),
            }
            
            result = supabase.table("collections").insert(collection_data).execute()
            
            if result.data:
                collection = result.data[0]
                
                # Add bookmarks to collection
                bookmark_ids = proposal.get("bookmark_ids", [])
                for bookmark_id in bookmark_ids:
                    try:
                        supabase.table("bookmark_collections").insert({
                            "collection_id": collection["id"],
                            "bookmark_id": bookmark_id,
                        }).execute()
                    except Exception:
                        pass  # Skip if bookmark doesn't exist or already added
                
                collection["bookmark_count"] = len(bookmark_ids)
                created_collections.append(collection)
        
        return jsonify({
            "message": f"Created {len(created_collections)} collections",
            "collections": created_collections,
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to create collections: {str(e)}"}), 500
