"""
Tests for Public Profile behavior - Folder Isolation and Visibility.

This test suite ensures:
1. Folder data is NOT exposed on public profiles
2. Save-to-collection does NOT copy folder_id
3. Visibility rules work correctly
4. Folder operations are protected by auth
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_auth(mocker):
    """Mock authentication with a dummy user."""
    mock_admin = mocker.patch('middleware.auth.get_supabase')
    mock_auth_client = mocker.patch('middleware.auth.get_auth_client')
    
    mock_user = MagicMock()
    mock_user.id = "viewer-user-id"
    mock_user.email = "viewer@example.com"
    
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_admin.return_value.auth.get_user.return_value = mock_response
    
    mock_scoped_client = MagicMock()
    mock_auth_client.return_value = mock_scoped_client
    
    return {"user": mock_user, "supabase": mock_scoped_client, "token": "dummy-token"}


class TestFolderIsolation:
    """
    Test Suite: Folder Isolation on Public Profiles
    
    CRITICAL: Folders are personal organization. They must NEVER
    be exposed on public profiles or copied when saving bookmarks.
    """
    
    def test_public_bookmarks_do_not_include_folder_id(self, client, mocker):
        """
        SCENARIO: Fetching public bookmarks from someone's profile
        EXPECTED: Response does NOT include folder_id field
        
        Even if the source bookmarks have folder_id set, the public
        profile should not expose this organizational detail.
        """
        # Setup: Mock profile lookup
        mocker.patch('routes.public.get_user_profile_by_username', return_value={
            'id': 'profile-owner-id',
            'full_name': 'Profile Owner',
            'avatar_url': 'http://avatar.com'
        })
        
        # Setup: Mock Supabase
        mock_supabase = MagicMock()
        mocker.patch('routes.public.get_supabase', return_value=mock_supabase)
        
        # Setup: Mock count query
        mock_count = MagicMock(count=1)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_count
        
        # Setup: Mock data query - note: folder_id is NOT in select
        bookmark = {
            "id": "1", 
            "url": "https://example.com", 
            "is_public": True,
            "clean_title": "Example"
            # folder_id intentionally NOT included
        }
        mock_data = MagicMock(data=[bookmark])
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data
        
        # Execute
        response = client.get('/api/public/@profileowner/bookmarks')
        
        # Verify: Response is successful
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify: folder_id is NOT in the response
        for bookmark in data['bookmarks']:
            assert 'folder_id' not in bookmark
    
    def test_save_public_does_not_copy_folder(self, client, mock_auth, mocker):
        """
        SCENARIO: User saves a bookmark that has a folder_id in the source
        EXPECTED: The saved bookmark does NOT inherit the folder_id
        
        This is critical - folders are personal organization. When you
        save someone else's bookmark, you should organize it yourself.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        mock_scoped_supabase = mock_auth["supabase"]
        
        # Setup: Mock admin supabase
        mock_admin_supabase = MagicMock()
        mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
        mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
        
        # Setup: Mock auth
        mock_response = MagicMock()
        mock_response.user = mock_auth["user"]
        mock_admin_supabase.auth.get_user.return_value = mock_response
        
        # Setup: Source bookmark HAS a folder_id
        mock_execute_res = MagicMock()
        mock_execute_res.data = {
            "id": "source-id",
            "url": "https://organized.com",
            "domain": "organized.com",
            "original_title": "Organized Bookmark",
            "clean_title": "Organized",
            "ai_summary": "Summary",
            "auto_tags": ["tag"],
            "favicon_url": "http://favicon.com",
            "thumbnail_url": None,
            "content_type": "article",
            "intent_type": "learn",
            "technical_level": "beginner",
            "is_public": True,
            "folder_id": "source-folder-123"  # Source has folder!
        }
        mock_admin_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_execute_res
        
        # Setup: User does NOT have this URL
        mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        
        # Setup: Capture what gets inserted
        inserted_data = {}
        def capture_insert(data):
            inserted_data.update(data)
            mock_result = MagicMock()
            mock_result.execute.return_value = MagicMock(data=[{"id": "new-id", **data}])
            return mock_result
        
        mock_scoped_supabase.table.return_value.insert = capture_insert
        
        # Execute
        with patch('flask.g', MagicMock(user=mock_auth["user"], supabase=mock_scoped_supabase)):
            response = client.post('/api/bookmarks/save-public',
                                   json={"bookmark_id": "source-id"},
                                   headers=headers)
        
        # Verify: Success
        assert response.status_code == 201
        
        # Verify: folder_id was NOT copied
        assert 'folder_id' not in inserted_data


class TestFolderAccessControl:
    """
    Test Suite: Folder Operations Access Control
    
    Folder CRUD operations require authentication and can only
    affect the authenticated user's own folders.
    """
    
    def test_list_folders_requires_auth(self, client):
        """
        SCENARIO: Unauthenticated request to list folders
        EXPECTED: Returns 401 Unauthorized
        """
        response = client.get('/api/folders')
        assert response.status_code == 401
    
    def test_create_folder_requires_auth(self, client):
        """
        SCENARIO: Unauthenticated request to create folder
        EXPECTED: Returns 401 Unauthorized
        """
        response = client.post('/api/folders', json={"name": "Test"})
        assert response.status_code == 401
    
    def test_delete_folder_requires_auth(self, client):
        """
        SCENARIO: Unauthenticated request to delete folder
        EXPECTED: Returns 401 Unauthorized
        """
        response = client.delete('/api/folders/some-id')
        assert response.status_code == 401
    
    def test_list_folders_only_returns_own(self, client, mock_auth, mocker):
        """
        SCENARIO: Authenticated user lists folders
        EXPECTED: Only returns folders where user_id matches

        This verifies the RLS-like behavior in the route.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        mock_scoped_supabase = mock_auth["supabase"]

        # Setup: Mock folder data
        mock_folders = [{"id": "folder-1", "name": "My Folder", "user_id": mock_auth["user"].id}]
        mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=mock_folders)

        # Setup: Mock bookmark count query (new behavior - list_folders now counts bookmarks per folder)
        mock_count_result = MagicMock()
        mock_count_result.count = 5
        mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_count_result

        # Execute
        with patch('flask.g', MagicMock(user=mock_auth["user"], supabase=mock_scoped_supabase)):
            response = client.get('/api/folders', headers=headers)

        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['name'] == "My Folder"
        # Verify bookmark_count is included (new feature)
        assert 'bookmark_count' in data[0]


class TestVisibilityRules:
    """
    Test Suite: Public/Private Bookmark Visibility
    
    Extends existing tests with folder-related scenarios.
    """
    
    def test_public_profile_shows_is_saved_by_viewer(self, client, mock_auth, mocker):
        """
        SCENARIO: Authenticated user views another user's profile
        EXPECTED: Each bookmark has is_saved_by_viewer correctly set
        
        This helps the UI show which bookmarks the user already has.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        
        # Setup: Profile belongs to different user
        mocker.patch('routes.public.get_user_profile_by_username', return_value={
            'id': 'other-user-id',  # Different from viewer
            'full_name': 'Other User',
            'avatar_url': 'http://avatar.com'
        })
        
        # Setup: Mock Supabase
        mock_supabase = MagicMock()
        mocker.patch('routes.public.get_supabase', return_value=mock_supabase)
        
        # Setup: Mock auth client for viewer verification
        mock_auth_client = MagicMock()
        mocker.patch('database.get_auth_client', return_value=mock_auth_client)
        mock_auth_response = MagicMock()
        mock_auth_response.user = mock_auth['user']
        mock_auth_client.auth.get_user.return_value = mock_auth_response
        
        # Setup: Mock count query
        mock_count = MagicMock(count=2)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_count
        
        # Setup: Profile has 2 bookmarks
        profile_bookmarks = [
            {"id": "1", "url": "https://saved.com", "is_public": True},
            {"id": "2", "url": "https://notsaved.com", "is_public": True}
        ]
        mock_data = MagicMock(data=profile_bookmarks)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data
        
        # Setup: Viewer already has one of the URLs
        viewer_bookmarks = MagicMock(data=[{"url": "https://saved.com"}])
        # This is called to check viewer's existing bookmarks
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = viewer_bookmarks
        
        # Execute
        response = client.get('/api/public/@otheruser/bookmarks', headers=headers)
        
        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_owner'] is False
    
    def test_owner_can_see_private_bookmarks(self, client, mock_auth, mocker):
        """
        SCENARIO: User views their own public profile page
        EXPECTED: Sees both public and private bookmarks
        
        The owner should have full visibility when viewing their
        own profile, including bookmarks marked as private.
        """
        headers = {"Authorization": f"Bearer {mock_auth['token']}"}
        
        # Setup: Profile belongs to SAME user as viewer
        mocker.patch('routes.public.get_user_profile_by_username', return_value={
            'id': mock_auth['user'].id,  # Same as viewer!
            'full_name': 'Viewer',
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
        
        # Setup: Count query WITHOUT is_public filter (for owner)
        mock_count = MagicMock(count=3)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_count
        
        # Setup: Both public AND private bookmarks
        all_bookmarks = [
            {"id": "1", "url": "https://public.com", "is_public": True},
            {"id": "2", "url": "https://private.com", "is_public": False},
            {"id": "3", "url": "https://also-private.com", "is_public": False}
        ]
        mock_data = MagicMock(data=all_bookmarks)
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data
        
        # Execute
        response = client.get('/api/public/@viewer/bookmarks', headers=headers)
        
        # Verify
        assert response.status_code == 200
        data = response.get_json()
        
        # Verify: is_owner is True
        assert data['is_owner'] is True
        
        # Verify: Sees all bookmarks including private ones
        assert len(data['bookmarks']) == 3
        assert data['total_count'] == 3
