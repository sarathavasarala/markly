import pytest
import os
from app import create_app


@pytest.fixture
def app():
    # Set dummy env vars for testing if not present
    os.environ['SUPABASE_URL'] = os.getenv('SUPABASE_URL', 'https://test.supabase.co')
    os.environ['SUPABASE_KEY'] = os.getenv('SUPABASE_KEY', 'test-key')
    os.environ['SUPABASE_SERVICE_KEY'] = os.getenv('SUPABASE_SERVICE_KEY', 'test-service-key')
    os.environ['AZURE_OPENAI_API_KEY'] = os.getenv('AZURE_OPENAI_API_KEY', 'test-openai-key')
    os.environ['AZURE_OPENAI_ENDPOINT'] = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com')
    
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def mock_supabase(mocker):
    """Mock supabase client."""
    mock_lib = mocker.patch('database.supabase')
    return mock_lib

@pytest.fixture
def mock_openai(mocker):
    """Mock OpenAI client."""
    mock_client = mocker.patch('services.extractor.client')
    return mock_client
