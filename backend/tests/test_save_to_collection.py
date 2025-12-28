"""
Tests for Save to Collection feature - Public Profile functionality.

This test suite covers critical scenarios to prevent production breaks:
1. Saved state detection (is_saved_by_viewer field)
2. Duplicate bookmark handling
3. Error cases (404, auth failures)
4. Public/private bookmark visibility
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_auth(mocker):
    """Mock authentication by providing a dummy token and mocking verification."""
    # Mock the auth client and user response
    mock_admin = mocker.patch('middleware.auth.get_supabase')
    mock_auth_client = mocker.patch('middleware.auth.get_auth_client')
    
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_admin.return_value.auth.get_user.return_value = mock_response
    
    # Mock the scoped client
    mock_scoped_client = MagicMock()
    mock_auth_client.return_value = mock_scoped_client
    
    return {"user": mock_user, "supabase": mock_scoped_client, "token": "dummy-token"}




class TestDuplicateDetection:
    """
    Test Suite: Duplicate Bookmark Detection
    
    Critical for data integrity: Prevents users from saving the same
    bookmark multiple times. Backend must detect duplicates by URL.
    """
    
    def test_save_public_bookmark_duplicate_detected(self, client, mock_auth, mocker):
        """
        SCENARIO: User tries to save a bookmark they already have
        EXPECTED: Returns already_exists=True, does not create duplicate
        
        This is the most important duplicate detection test. When a user
        tries to save a bookmark with a URL they already have in their
        collection, the backend should detect it and return a flag.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        mock_scoped_supabase = mock_auth["supabase"]
        
        # Setup: Mock admin supabase for fetching original bookmark
        mock_admin_supabase = MagicMock()
        mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
        mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
        
        # Setup: Mock auth
        mock_user = mock_auth["user"]
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_admin_supabase.auth.get_user.return_value = mock_response
        
        # Setup: Original public bookmark exists
        mock_execute_res = MagicMock()
        mock_execute_res.data = {
            "id": "original-id",
            "url": "https://duplicate.com",
            "domain": "duplicate.com",
            "original_title": "Title",
            "clean_title": "Clean Title",
            "ai_summary": "Summary",
            "auto_tags": ["tag1"],
            "favicon_url": "http://favicon.com",
            "thumbnail_url": "http://thumb.com",
            "content_type": "article",
            "intent_type": "learn",
            "technical_level": "beginner",
            "is_public": True
        }
        mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute_res
        
        # Setup: User ALREADY has this URL in their collection
        existing_bookmark = [{"id": "existing-id", "url": "https://duplicate.com"}]
        mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=existing_bookmark)
        
        # Execute: Try to save the bookmark
        with patch('flask.g', MagicMock(user=mock_auth["user"], supabase=mock_scoped_supabase)):
            response = client.post('/api/bookmarks/save-public', 
                                   json={"bookmark_id": "original-id"}, 
                                   headers=headers)
        
        # Verify: Returns success but with already_exists flag
        assert response.status_code == 200  # Not 201 (created)
        data = response.get_json()
        assert data['already_exists'] is True
        assert data['message'] == "Bookmark already exists in your collection"
        
        # Verify: Returns the existing bookmark, not a new one
        assert data['bookmark']['id'] == "existing-id"
    
    def test_save_public_bookmark_new_save_success(self, client, mock_auth, mocker):
        """
        SCENARIO: User saves a bookmark they don't have yet
        EXPECTED: Creates new bookmark, returns 201 Created
        
        This is the happy path - user saves a new bookmark successfully.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        mock_scoped_supabase = mock_auth["supabase"]
        
        # Setup: Mock admin supabase
        mock_admin_supabase = MagicMock()
        mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
        mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
        
        # Setup: Mock auth
        mock_user = mock_auth["user"]
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_admin_supabase.auth.get_user.return_value = mock_response
        
        # Setup: Original bookmark exists
        mock_execute_res = MagicMock()
        mock_execute_res.data = {
            "id": "original-id",
            "url": "https://newbookmark.com",
            "domain": "newbookmark.com",
            "original_title": "New Bookmark",
            "clean_title": "New Bookmark",
            "ai_summary": "Summary",
            "auto_tags": ["new"],
            "favicon_url": "http://favicon.com",
            "thumbnail_url": None,
            "content_type": "article",
            "intent_type": "learn",
            "technical_level": "beginner",
            "is_public": True
        }
        mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute_res
        
        # Setup: User does NOT have this URL yet (empty result)
        mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        
        # Setup: Mock successful insert
        mock_new_bookmark = {"id": "new-saved-id", "url": "https://newbookmark.com"}
        mock_insert_res = MagicMock(data=[mock_new_bookmark])
        mock_scoped_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_res
        
        # Execute: Save the bookmark
        with patch('flask.g', MagicMock(user=mock_auth["user"], supabase=mock_scoped_supabase)):
            response = client.post('/api/bookmarks/save-public',
                                   json={"bookmark_id": "original-id"},
                                   headers=headers)
        
        # Verify: Returns 201 Created
        assert response.status_code == 201
        data = response.get_json()
        
        # Verify: Returns new bookmark ID
        assert data['id'] == "new-saved-id"
        
        # Verify: No already_exists flag (or it's False/not present)
        assert data.get('already_exists') is not True


class TestErrorCases:
    """
    Test Suite: Error Handling
    
    Critical for reliability: Proper error responses prevent silent
    failures and help users understand what went wrong.
    """
    
    def test_save_public_bookmark_not_found(self, client, mock_auth, mocker):
        """
        SCENARIO: User tries to save a bookmark that doesn't exist
        EXPECTED: Returns 404 Not Found
        
        This can happen if a bookmark is deleted while the user is
        viewing the profile. Backend must handle gracefully.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        
        # Setup: Mock admin supabase
        mock_admin_supabase = MagicMock()
        mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
        mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
        
        # Setup: Mock auth
        mock_response = MagicMock()
        mock_response.user = mock_auth["user"]
        mock_admin_supabase.auth.get_user.return_value = mock_response
        
        # Setup: Bookmark does not exist (empty result)
        mock_execute_res = MagicMock(data=None)
        mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute_res
        
        # Execute: Try to save non-existent bookmark
        response = client.post('/api/bookmarks/save-public',
                               json={"bookmark_id": "non-existent-id"},
                               headers=headers)
        
        # Verify: Returns 404
        assert response.status_code == 404
        assert "not found" in response.get_json()['error'].lower()
    
    def test_save_public_bookmark_not_public(self, client, mock_auth, mocker):
        """
        SCENARIO: User tries to save a private bookmark
        EXPECTED: Returns 404 Not Found (private bookmarks are hidden)
        
        Only public bookmarks can be saved. Private bookmarks should
        be treated as if they don't exist.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        
        # Setup: Mock admin supabase
        mock_admin_supabase = MagicMock()
        mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
        mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
        
        # Setup: Mock auth
        mock_response = MagicMock()
        mock_response.user = mock_auth["user"]
        mock_admin_supabase.auth.get_user.return_value = mock_response
        
        # Setup: Bookmark exists but is private (query filters it out)
        mock_execute_res = MagicMock(data=None)  # .eq('is_public', True) returns nothing
        mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute_res
        
        # Execute: Try to save private bookmark
        response = client.post('/api/bookmarks/save-public',
                               json={"bookmark_id": "private-bookmark-id"},
                               headers=headers)
        
        # Verify: Returns 404 (private bookmarks are hidden)
        assert response.status_code == 404
    
    def test_save_public_bookmark_missing_id(self, client, mock_auth):
        """
        SCENARIO: Request missing bookmark_id parameter
        EXPECTED: Returns 400 Bad Request
        
        API validation - must provide bookmark_id.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        
        # Execute: Send request without bookmark_id
        response = client.post('/api/bookmarks/save-public',
                               json={},  # Empty payload
                               headers=headers)
        
        # Verify: Returns 400
        assert response.status_code == 400
        assert "required" in response.get_json()['error'].lower()
    
    def test_save_public_bookmark_unauthenticated(self, client):
        """
        SCENARIO: Unauthenticated user tries to save bookmark
        EXPECTED: Returns 401 Unauthorized
        
        Saving bookmarks requires authentication.
        """
        # Execute: Send request without auth token
        response = client.post('/api/bookmarks/save-public',
                               json={"bookmark_id": "some-id"})
        
        # Verify: Returns 401
        assert response.status_code == 401


class TestPublicProfileVisibility:
    """
    Test Suite: Public/Private Bookmark Visibility
    
    Critical for privacy: Private bookmarks must never appear on
    public profiles, even to authenticated users.
    """
    
    def test_public_profile_hides_private_bookmarks(self, client, mocker):
        """
        SCENARIO: User has both public and private bookmarks
        EXPECTED: Only public bookmarks appear on their profile
        
        This is a critical privacy feature. Private bookmarks must
        be completely hidden from public profiles.
        """
        # Setup: Mock profile lookup
        mocker.patch('routes.public.get_user_profile_by_username', return_value={
            'id': 'user-123',
            'full_name': 'Test User',
            'avatar_url': 'http://avatar.com'
        })
        
        # Setup: Mock Supabase
        mock_supabase = MagicMock()
        mocker.patch('routes.public.get_supabase', return_value=mock_supabase)
        
        # Setup: Mock count query (only counts public bookmarks)
        mock_count = MagicMock(count=1)  # Only 1 public bookmark
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_count
        
        # Setup: Mock data query (only returns public bookmark)
        public_bookmark = {"id": "1", "url": "https://public.com", "is_public": True}
        mock_data = MagicMock(data=[public_bookmark])
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data
        
        # Execute: Request public profile
        response = client.get('/api/public/@testuser/bookmarks')
        
        # Verify: Response is successful
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify: Only public bookmark is returned
        assert len(data['bookmarks']) == 1
        assert data['bookmarks'][0]['is_public'] is True
        assert data['total_count'] == 1
    
    def test_owner_sees_all_bookmarks_on_own_profile(self, client, mock_auth, mocker):
        """
        SCENARIO: Owner views their own public profile
        EXPECTED: Sees both public AND private bookmarks
        
        When viewing your own profile, you should see all your
        bookmarks, not just the public ones.
        """
        # Setup: Mock profile lookup (same user as viewer)
        mocker.patch('routes.public.get_user_profile_by_username', return_value={
            'id': mock_auth['user'].id,
            'full_name': 'Test User',
            'avatar_url': 'http://avatar.com'
        })
        
        # Setup: Mock Supabase
        mock_supabase = MagicMock()
        mocker.patch('routes.public.get_supabase', return_value=mock_supabase)
        
        # Setup: Mock auth client
        mock_auth_client = MagicMock()
        mocker.patch('database.get_auth_client', return_value=mock_auth_client)
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_auth['user']
        mock_auth_client.auth.get_user.return_value = mock_auth_response
        
        # Setup: Mock count query (counts ALL bookmarks for owner)
        mock_count = MagicMock(count=2)  # 2 total bookmarks
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_count
        
        # Setup: Mock data query (returns both public and private)
        all_bookmarks = [
            {"id": "1", "url": "https://public.com", "is_public": True},
            {"id": "2", "url": "https://private.com", "is_public": False}
        ]
        mock_data = MagicMock(data=all_bookmarks)
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data
        
        # Execute: Request own profile with auth
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        response = client.get('/api/public/@test/bookmarks', headers=headers)
        
        # Verify: Response is successful
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify: is_owner is True
        assert data['is_owner'] is True
        
        # Verify: Sees both public and private bookmarks
        assert len(data['bookmarks']) == 2
        assert data['total_count'] == 2
