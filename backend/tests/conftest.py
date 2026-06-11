import os

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    os.environ["APP_ENV"] = "test"
    os.environ["MARKLY_DB_PATH"] = str(tmp_path / "markly-test.db")
    os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY", "test-openai-key")
    os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://test.openai.azure.com",
    )

    import config
    config.Config.MARKLY_DB_PATH = os.environ["MARKLY_DB_PATH"]
    config.Config.AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
    config.Config.AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
    config.Config.JINA_READER_API_KEY = None

    from app import create_app

    app = create_app()
    app.config.update({"TESTING": True})
    monkeypatch.setattr("routes.bookmarks.archive_bookmark_async", lambda _bookmark_id: None)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
