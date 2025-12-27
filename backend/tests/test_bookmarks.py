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

def test_list_bookmarks(client, mock_auth, mocker):
    headers = {"Authorization": f"Bearer {mock_auth['token']}"}
    mock_supabase = mock_auth["supabase"]
    
    # Setup mock response
    mock_result = MagicMock()
    mock_result.data = [{"id": "1", "url": "https://example.com"}]
    mock_result.count = 1
    
    # Build the chain of calls
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = mock_result
    
    response = client.get('/api/bookmarks', headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["bookmarks"]) == 1
    assert data["bookmarks"][0]["url"] == "https://example.com"

def test_create_bookmark_invalid_url(client, mock_auth):
    headers = {"Authorization": f"Bearer {mock_auth['token']}"}
    response = client.post('/api/bookmarks', json={"url": "not-a-url"}, headers=headers)
    assert response.status_code == 400
    assert "Invalid URL format" in response.get_json()["error"]

def test_create_bookmark_success(client, mock_auth, mocker):
    headers = {"Authorization": f"Bearer {mock_auth['token']}"}
    mock_supabase = mock_auth["supabase"]
    
    # Mock existing check (empty)
    mock_existing = MagicMock(data=[])
    # The route calls g.supabase which we mocked to return mock_scoped_client
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_existing
    
    # Mock insert
    mock_insert_result = MagicMock(data=[{"id": "new-id", "url": "https://new.com"}])
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_result
    
    # Mock background enrichment trigger
    mocker.patch('routes.bookmarks.enrich_bookmark_async')
    
    response = client.post('/api/bookmarks', json={"url": "https://new.com"}, headers=headers)
    assert response.status_code == 201
    assert response.get_json()["id"] == "new-id"

def test_bookmark_isolation_delete(client, mock_auth, mocker):
    """Scenario 1: No one else can delete my bookmarks."""
    headers = {"Authorization": f"Bearer {mock_auth['token']}"}
    mock_supabase = mock_auth["supabase"]
    
    # Mock delete returning empty data (as if item doesn't exist or RLS blocked it)
    mock_result = MagicMock(data=[])
    mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_result
    
    response = client.delete('/api/bookmarks/some-other-id', headers=headers)
    # The route returns 404 if data is empty (filtered by RLS)
    assert response.status_code == 404

def test_save_public_bookmark_creation(client, mock_auth, mocker):
    """Scenario 2 & 3: Save from public profile creates independent copy."""
    headers = {"Authorization": f"Bearer {mock_auth['token']}"}
    mock_scoped_supabase = mock_auth["supabase"]
    
    # Mock the admin fetch of the original public bookmark
    # The route does: from database import get_supabase; admin_supabase = get_supabase()
    mock_admin_supabase = MagicMock()
    # Patch it in both places to be safe
    mocker.patch('database.get_supabase', return_value=mock_admin_supabase)
    mocker.patch('middleware.auth.get_supabase', return_value=mock_admin_supabase)
    
    # Setup mock_admin_supabase to handle auth too
    mock_user = mock_auth["user"]
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_admin_supabase.auth.get_user.return_value = mock_response
    
    # Original bookmark data - must include all keys the route expects to copy
    mock_execute_res = MagicMock()
    mock_execute_res.data = {
        "id": "original", 
        "url": "https://pub.com", 
        "domain": "pub.com",
        "original_title": "Original Title", 
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
    
    # 2. Mock existing check (empty) on the scoped client
    mock_scoped_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    
    # 3. Mock the insert of the NEW record on the scoped client
    mock_new_id = "copied-id"
    mock_insert_res = MagicMock()
    mock_insert_res.data = [{"id": mock_new_id, "url": "https://pub.com"}]
    mock_scoped_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_res
    
    # Mock g.supabase to be the mock_scoped_supabase
    with patch('flask.g', MagicMock(user=mock_auth["user"], supabase=mock_scoped_supabase)):
        response = client.post('/api/bookmarks/save-public', json={"bookmark_id": "original"}, headers=headers)
        assert response.status_code == 201
        assert response.get_json()["id"] == mock_new_id

def test_public_profile_visibility(client, mocker):
    """Scenario 4: Public profile only shows public bookmarks."""
    # 1. Mock get_user_profile_by_username
    mocker.patch('routes.public.get_user_profile_by_username', return_value={
        'id': 'user-123',
        'full_name': 'Test User',
        'avatar_url': 'http://avatar.com'
    })

    # 2. Mock get_supabase
    mock_supabase = MagicMock()
    mocker.patch('routes.public.get_supabase', return_value=mock_supabase)

    # Mock the count query
    mock_count = MagicMock(count=1)
    mock_query = mock_supabase.table.return_value.select.return_value
    mock_query.eq.return_value.eq.return_value.execute.return_value = mock_count

    # Mock the data query
    mock_item = {"id": "1", "url": "https://public-only.com", "is_public": True}
    mock_data = MagicMock(data=[mock_item])
    mock_query.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_data

    # Use the correct route: /api/public/@username/bookmarks
    response = client.get('/api/public/@testuser/bookmarks')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["bookmarks"]) == 1
    assert data["bookmarks"][0]["is_public"] is True
