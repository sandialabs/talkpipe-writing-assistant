"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

# Set a known token for testing before importing the app
import writing_assistant.app.main as main_module
main_module.AUTH_TOKEN = "test-token"

from writing_assistant.app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    from writing_assistant.core.definitions import Metadata

    metadata = Metadata()
    metadata.writing_style = "formal"
    metadata.target_audience = "academic"
    metadata.tone = "professional"
    metadata.background_context = "test context"
    metadata.generation_directive = "be clear and concise"
    metadata.word_limit = 100
    return metadata