"""Search routes."""
from flask import Blueprint, request, jsonify, g

from middleware.auth import require_auth
from services.openai_service import AzureOpenAIService

search_bp = Blueprint("search", __name__)


@search_bp.route("", methods=["GET"])
@require_auth
def search_bookmarks():
    """
    Search bookmarks using keyword or semantic search.
    
    Query params:
    - q: search query
    - mode: 'keyword' or 'semantic' (default: keyword)
    - limit: max results (default: 20)
    - offset: pagination offset (default: 0)
    - domain: filter by domain
    - content_type: filter by content type
    - tag: filter by tag
    """
    query = request.args.get("q", "").strip()
    mode = request.args.get("mode", "keyword")
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 100)
    offset = request.args.get("offset", 0, type=int)
    
    # Filters
    domain = request.args.get("domain")
    content_type = request.args.get("content_type")
    tag = request.args.get("tag")
    
    if not query and not tag:
        return jsonify({"error": "Search query is required"}), 400
    
    try:
        supabase = g.supabase
        
        if mode == "semantic":
            results = _semantic_search(supabase, query, limit, domain, content_type, tag)
        else:
            results = _keyword_search(supabase, query, limit, offset, domain, content_type, tag)
        
        # Save search to history
        try:
            supabase.table("search_history").insert({
                "query": query,
                "results_count": len(results),
            }).execute()
        except Exception:
            pass  # Don't fail search if history save fails
        
        return jsonify({
            "query": query,
            "mode": mode,
            "results": results,
            "count": len(results),
        })
        
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


def _keyword_search(supabase, query: str, limit: int, offset: int, 
                    domain: str = None, content_type: str = None, tag: str = None) -> list:
    """Perform keyword search using ILIKE with tag support."""
    
    base_query = supabase.table("bookmarks").select(
        "id, url, domain, original_title, clean_title, ai_summary, "
        "auto_tags, favicon_url, thumbnail_url, content_type, intent_type, "
        "created_at, access_count, enrichment_status"
    ).eq("user_id", g.user.id).eq("enrichment_status", "completed")
    
    # Apply filters
    if domain:
        base_query = base_query.eq("domain", domain)
    if content_type:
        base_query = base_query.eq("content_type", content_type)
    if tag:
        base_query = base_query.contains("auto_tags", [tag])
    
    # Use a broad ILIKE OR across key text fields and include tag contains match
    if query:
        like_query = f"%{query}%"
        base_query = base_query.or_(
            f"clean_title.ilike.{like_query},"
            f"ai_summary.ilike.{like_query},"
            f"original_title.ilike.{like_query},"
            f"auto_tags.cs.{{{query}}}"
        )
    
    result = base_query.order(
        "created_at", desc=True
    ).range(offset, offset + limit - 1).execute()
    
    return result.data


def _semantic_search(supabase, query: str, limit: int,
                     domain: str = None, content_type: str = None, tag: str = None) -> list:
    """Perform semantic search using vector similarity."""
    
    # Generate embedding for the query
    query_embedding = AzureOpenAIService.generate_embedding(query)
    
    # Use the match_bookmarks RPC function
    # Note: RPC functions in Supabase are usually SECURITY INVOKER by default,
    # so they will respect the RLS of the user represented by the auth token.
    result = supabase.rpc("match_bookmarks", {
        "query_embedding": query_embedding,
        "match_threshold": 0.3,  # Lower threshold for more results
        "match_count": limit * 2,  # Get more to filter
    }).execute()
    
    # The match_bookmarks RPC already filters by auth.uid() in the SQL function,
    # so no additional user_id filter is needed here.
    results = result.data

    # Hydrate missing timestamps from bookmarks table (RPC may omit created_at)
    try:
        ids = [r.get("id") for r in results if r.get("id")]
        if ids:
            meta = supabase.table("bookmarks").select(
                "id, created_at, updated_at, last_accessed_at"
            ).in_("id", ids).execute()
            meta_map = {m["id"]: m for m in meta.data}
            for r in results:
                meta_row = meta_map.get(r.get("id"))
                if meta_row:
                    # Only fill if missing to avoid overwriting
                    for key in ("created_at", "updated_at", "last_accessed_at"):
                        if not r.get(key):
                            r[key] = meta_row.get(key)
    except Exception:
        pass  # If hydration fails, continue without blocking search
    
    # Apply post-filters (since RPC doesn't support filtering)
    if domain:
        results = [r for r in results if r.get("domain") == domain]
    if content_type:
        results = [r for r in results if r.get("content_type") == content_type]
    if tag:
        results = [r for r in results if tag in (r.get("auto_tags") or [])]
    
    # Add similarity score to results
    for r in results:
        r["similarity"] = round(r.get("similarity", 0), 3)
    
    return results[:limit]


@search_bp.route("/history", methods=["GET"])
@require_auth
def get_search_history():
    """Get recent search history."""
    limit = request.args.get("limit", 10, type=int)
    limit = min(limit, 50)
    
    try:
        supabase = g.supabase
        
        result = supabase.table("search_history").select(
            "query, results_count, created_at"
        ).eq("user_id", g.user.id).order("created_at", desc=True).limit(limit).execute()
        
        # Deduplicate by query (keep most recent)
        seen = set()
        unique_searches = []
        for search in result.data:
            if search["query"] not in seen:
                seen.add(search["query"])
                unique_searches.append(search)
        
        return jsonify({"history": unique_searches})
        
    except Exception as e:
        return jsonify({"error": f"Failed to get search history: {str(e)}"}), 500

