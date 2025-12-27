import pytest
from services.content_extractor import ContentExtractor
from unittest.mock import patch, MagicMock

def test_extract_domain():
    url = "https://www.example.com/some/path"
    result = ContentExtractor.extract(url)
    assert result["domain"] == "example.com"

@patch('requests.get')
def test_extract_via_beautifulsoup(mock_get):
    # Mock response
    mock_response = MagicMock()
    mock_response.content = b"<html><head><title>Test Title</title><meta name='description' content='Test Description'></head><body><main>Test Content</main></body></html>"
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    url = "https://example.com"
    # Ensure JINA_READER_API_KEY is None so it falls back to BS
    with patch('config.Config.JINA_READER_API_KEY', None):
        result = ContentExtractor.extract(url)
    
    assert result["title"] == "Test Title"
    assert result["description"] == "Test Description"
    assert "Test Content" in result["content"]

@patch('requests.get')
def test_extract_via_jina(mock_get):
    # Mock Jina response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "title": "Jina Title",
            "description": "Jina Description",
            "content": "Jina Content"
        }
    }
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    url = "https://example.com"
    # Set JINA_READER_API_KEY to trigger Jina extraction
    with patch('config.Config.JINA_READER_API_KEY', 'test-key'):
        result = ContentExtractor.extract(url)
    
    assert result["title"] == "Jina Title"
    assert result["description"] == "Jina Description"
    assert result["content"] == "Jina Content"
