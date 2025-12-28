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
                # Also get bookmark count for this user
                count_res = supabase.table('bookmarks').select('id', count='exact') \
                    .eq('user_id', u_id).eq('is_public', True).execute()
                bookmark_count = count_res.count or 0
                
                return {
                    'id': u_id,
                    'email': u_email,
                    'avatar_url': u_metadata.get('avatar_url') or u_metadata.get('picture') if u_metadata else None,
                    'full_name': u_metadata.get('full_name') or u_metadata.get('name') if u_metadata else None,
                    'bookmark_count': bookmark_count
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
    viewer_user_id = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            # Use a fresh client to verify this specific token
            # to avoid any singleton state issues
            from database import get_auth_client
            auth_client = get_auth_client(token)
            user_resp = auth_client.auth.get_user()
            if user_resp and user_resp.user:
                viewer_user_id = user_resp.user.id
                if viewer_user_id == user_id:
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
        
        bookmarks = result.data or []
        
        # Check which bookmarks the viewer has already saved
        if viewer_user_id and not is_owner:
            # Get all URLs the viewer has saved
            viewer_bookmarks = supabase.table('bookmarks') \
                .select('url') \
                .eq('user_id', viewer_user_id) \
                .execute()
            
            viewer_urls = {b['url'] for b in (viewer_bookmarks.data or [])}
            
            # Mark bookmarks that are already saved
            for bookmark in bookmarks:
                bookmark['is_saved_by_viewer'] = bookmark['url'] in viewer_urls
        else:
            # Owner or unauthenticated - not saved
            for bookmark in bookmarks:
                bookmark['is_saved_by_viewer'] = False
        
        return jsonify({
            'bookmarks': bookmarks,
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


@public_bp.route('/@<username>/subscribers', methods=['GET'])
@require_auth
def list_subscribers(username: str):
    """List subscribers for a curator (owner only)."""
    user_email = getattr(g.user, 'email', None)
    
    # Simple owner check: email prefix must match username
    if not user_email or user_email.split('@')[0].lower() != username.lower():
        # As an extra safety, check if it's the same ID if we can't trust email prefix
        profile = get_user_profile_by_username(username)
        if not profile or profile['id'] != g.user.id:
            return jsonify({'error': 'Unauthorized'}), 401
            
    try:
        supabase = get_supabase()
        response = supabase.table('subscribers') \
            .select('email, subscribed_at') \
            .eq('curator_username', username.lower()) \
            .is_('unsubscribed_at', 'null') \
            .order('subscribed_at', desc=True) \
            .execute()
            
        return jsonify({'subscribers': response.data or []})
    except Exception as e:
        logger.error(f"Error listing subscribers for {username}: {str(e)}")
        return jsonify({'error': f'Failed to list subscribers: {str(e)}'}), 500


@public_bp.route('/@<username>/subscription/check', methods=['GET'])
@require_auth
def check_subscription(username: str):
    """Check if the current user is subscribed to this curator."""
    user_email = getattr(g.user, 'email', None)
    if not user_email:
        return jsonify({'is_subscribed': False})
        
    supabase = get_supabase()
    try:
        response = supabase.table('subscribers') \
            .select('id') \
            .eq('curator_username', username.lower()) \
            .eq('email', user_email.lower()) \
            .is_('unsubscribed_at', 'null') \
            .execute()
            
        return jsonify({'is_subscribed': len(response.data) > 0})
    except Exception as e:
        return jsonify({'is_subscribed': False})


@public_bp.route('/@<username>/unsubscribe', methods=['POST'])
def unsubscribe_from_curator(username: str):
    """Unsubscribe from a curator's digest."""
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    
    # If not provided in body, try to get from logged-in user
    if not email:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from database import get_supabase
                admin_client = get_supabase()
                user_resp = admin_client.auth.get_user(auth_header[7:])
                if user_resp and user_resp.user:
                    email = user_resp.user.email.lower().strip()
            except:
                pass

    if not email:
        return jsonify({'error': 'Email required to unsubscribe'}), 400
        
    supabase = get_supabase()
    try:
        # We perform a soft delete by setting unsubscribed_at
        supabase.table('subscribers') \
            .update({'unsubscribed_at': 'now()'}) \
            .eq('curator_username', username.lower()) \
            .eq('email', email) \
            .execute()
            
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Unsubscribe error: {e}")
        return jsonify({'error': 'Failed to unsubscribe'}), 500


@public_bp.route('/@<username>/subscribers/<subscriber_email>', methods=['DELETE'])
@require_auth
def delete_subscriber(username: str, subscriber_email: str):
    """Delete a subscriber from your list (owner only)."""
    user_email = getattr(g.user, 'email', None)
    
    # Verify owner
    if not user_email or user_email.split('@')[0].lower() != username.lower():
        profile = get_user_profile_by_username(username)
        if not profile or profile['id'] != g.user.id:
            return jsonify({'error': 'Unauthorized'}), 401
            
    try:
        supabase = get_supabase()
        # Hard delete because the curator doesn't want them anymore
        supabase.table('subscribers') \
            .delete() \
            .eq('curator_username', username.lower()) \
            .eq('email', subscriber_email.lower()) \
            .execute()
            
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting subscriber {subscriber_email}: {e}")
        return jsonify({'error': 'Failed to delete subscriber'}), 500


@public_bp.route('/account', methods=['DELETE'])
@require_auth
def delete_account():
    """Completely delete the user's account and all data."""
    user_id = g.user.id
    user_email = g.user.email
    username = user_email.split('@')[0].lower()
    
    try:
        supabase = get_supabase()
        
        # 1. Delete all bookmarks (RLS might handle this, but being explicit)
        supabase.table('bookmarks').delete().eq('user_id', user_id).execute()
        
        # 2. Delete all search history
        supabase.table('search_history').delete().eq('user_id', user_id).execute()
        
        # 3. Delete all people SUBSCRIBED TO the user
        supabase.table('subscribers').delete().eq('curator_username', username).execute()
        
        # 4. Delete the user's own SUBSCRIPTIONS to others
        supabase.table('subscribers').delete().eq('email', user_email).execute()
        
        # 5. Finally, delete the auth user (requires service role)
        # Note: In a production app, you might want to sign them out first or do this via admin client
        supabase.auth.admin.delete_user(user_id)
        
        return jsonify({'success': True, 'message': 'Account and all data deleted'})
    except Exception as e:
        logger.error(f"Error deleting account for {user_id}: {e}")
        return jsonify({'error': f'Failed to delete account: {str(e)}'}), 500


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
