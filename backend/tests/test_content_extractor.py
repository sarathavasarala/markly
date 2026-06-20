from services.content_extractor import ContentExtractor
from unittest.mock import patch, MagicMock


def test_extract_domain():
    url = "https://www.example.com/some/path"
    with patch('config.Config.JINA_READER_API_KEY', None), patch.object(ContentExtractor, '_extract_via_beautifulsoup', return_value={}):
        result = ContentExtractor.extract(url)
    assert result["domain"] == "example.com"


@patch('requests.get')
def test_extract_via_beautifulsoup(mock_get):
    # Mock response
    mock_response = MagicMock()
    html_content = (
        b"<html><head><title>Test Title</title>"
        b"<meta name='description' content='Test Description'></head>"
        b"<body><main>Test Content</main></body></html>"
    )
    mock_response.content = html_content
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


@patch('requests.get')
def test_extract_bypass_jina(mock_get):
    # Mock fallback BeautifulSoup/local response
    mock_response = MagicMock()
    mock_response.content = (
        b"<html><head><title>Fallback Title</title></head>"
        b"<body><main>Fallback Local Content and more text to bypass threshold</main></body></html>"
    )
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    url = "https://example.com"
    # Even if JINA_READER_API_KEY is configured, bypass_jina=True should skip Jina
    with patch('config.Config.JINA_READER_API_KEY', 'test-key'):
        with patch.object(ContentExtractor, '_extract_via_jina') as mock_jina:
            result = ContentExtractor.extract(url, bypass_jina=True)
            mock_jina.assert_not_called()

    assert result["title"] == "Fallback Title"
    assert "Fallback Local Content" in result["content"]
