import logging
from flask import Blueprint, jsonify, request, g
from database import get_supabase
from middleware.auth import require_auth

logger = logging.getLogger(__name__)
public_bp = Blueprint('public', __name__)


def get_user_profile_by_username(username: str) -> dict | None:
    """
    Get user profile info from username.
    """
    supabase = get_supabase()
    
    try:
        users = supabase.auth.admin.list_users()
        user_list = users.users if hasattr(users, 'users') else users
        
        for user in user_list:
            # Handle both object and dict types
            u_email = getattr(user, 'email', None) or user.get('email') if isinstance(user, dict) else getattr(user, 'email', None)
            u_id = getattr(user, 'id', None) or user.get('id') if isinstance(user, dict) else getattr(user, 'id', None)
            u_metadata = getattr(user, 'user_metadata', None) or user.get('user_metadata') if isinstance(user, dict) else getattr(user, 'user_metadata', None)
            
            if u_email and u_email.split('@')[0].lower() == username.lower():
                return {
                    'id': u_id,
                    'email': u_email,
                    'avatar_url': u_metadata.get('avatar_url') or u_metadata.get('picture') if u_metadata else None,
                    'full_name': u_metadata.get('full_name') or u_metadata.get('name') if u_metadata else None
                }
        return None
    except Exception as e:
        print(f"Error looking up user by username '{username}': {e}")
        return None


@public_bp.route('/@<username>/bookmarks', methods=['GET'])
def get_public_bookmarks(username: str):
    """Get public bookmarks for a user's public profile."""
    
    profile = get_user_profile_by_username(username)
    if not profile:
        return jsonify({'error': 'User not found'}), 404
    
    user_id = profile['id']
    supabase = get_supabase()
    
    # Check if the requester is the owner
    is_owner = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            # Use a fresh client to verify this specific token
            # to avoid any singleton state issues
            from database import get_auth_client
            auth_client = get_auth_client(token)
            user_resp = auth_client.auth.get_user()
            if user_resp and user_resp.user and user_resp.user.id == user_id:
                is_owner = True
        except Exception as auth_err:
            logger.debug(f"Auth check failed for public profile: {auth_err}")
            pass

    try:
        # Get total count of public bookmarks (or all if owner)
        count_query = supabase.table('bookmarks') \
            .select('id', count='exact') \
            .eq('user_id', user_id)
        
        if not is_owner:
            count_query = count_query.eq('is_public', True)
            
        count_res = count_query.execute()
        total_count = count_res.count or 0

        # Build data query
        query = supabase.table('bookmarks') \
            .select('id, url, original_title, clean_title, user_description, ai_summary, auto_tags, domain, favicon_url, created_at, is_public') \
            .eq('user_id', user_id)
        
        # If not owner, only show public bookmarks
        if not is_owner:
            query = query.eq('is_public', True)
            
        result = query.order('created_at', desc=True) \
            .limit(100) \
            .execute()
        
        return jsonify({
            'bookmarks': result.data or [],
            'total_count': total_count,
            'username': username,
            'is_owner': is_owner,
            'profile': {
                'avatar_url': profile.get('avatar_url'),
                'full_name': profile.get('full_name')
            }
        })
    except Exception as e:
        logger.error(f"Error fetching public bookmarks for {username}: {str(e)}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@public_bp.route('/@<username>/subscribe', methods=['POST'])
def subscribe_to_curator(username: str):
    """Subscribe to a curator's digest."""
    
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    
    supabase = get_supabase()
    
    try:
        # Insert subscription
        response = supabase.table('subscribers').insert({
            'curator_username': username.lower(),
            'email': email
        }).execute()
        
        return jsonify({'success': True, 'message': 'Subscribed successfully'})
    except Exception as e:
        error_msg = str(e)
        if '23505' in error_msg:  # Unique constraint violation
            return jsonify({'error': 'Already subscribed'}), 409
        print(f"Subscribe error: {e}")
        return jsonify({'error': 'Failed to subscribe'}), 500


@public_bp.route('/@<username>/subscribers/count', methods=['GET'])
def get_subscriber_count(username: str):
    """Get subscriber count for a curator (only visible to owner, but endpoint is public for now)."""
    
    supabase = get_supabase()
    
    try:
        response = supabase.table('subscribers') \
            .select('id', count='exact') \
            .eq('curator_username', username.lower()) \
            .is_('unsubscribed_at', 'null') \
            .execute()
        
        return jsonify({'count': response.count or 0})
    except Exception as e:
        print(f"Error getting subscriber count: {e}")
        return jsonify({'count': 0})


@public_bp.route('/bookmarks/<bookmark_id>/visibility', methods=['PATCH'])
@require_auth
def toggle_bookmark_visibility(bookmark_id: str):
    """Toggle a bookmark's public/private status."""
    
    user_id = g.user.id
    
    data = request.get_json()
    is_public = data.get('is_public', True)
    
    # Use the user-scoped supabase client from g.supabase
    # which has the correct JWT and respects RLS
    try:
        response = g.supabase.table('bookmarks') \
            .update({'is_public': is_public}) \
            .eq('id', bookmark_id) \
            .execute()
        
        if not response.data:
            return jsonify({'error': 'Bookmark not found or access denied'}), 404
        
        return jsonify({'success': True, 'is_public': is_public})
    except Exception as e:
        logger.error(f"Error updating visibility for bookmark {bookmark_id}: {e}")
        return jsonify({'error': f'Failed to update visibility: {str(e)}'}), 500
