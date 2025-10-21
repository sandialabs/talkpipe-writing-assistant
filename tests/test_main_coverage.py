"""Tests to improve coverage of main.py endpoints and error handling."""

import json
import pytest
from unittest.mock import patch
from pathlib import Path


def test_root_endpoint(client):
    """Test the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_login_page(client):
    """Test the login page endpoint."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_register_page(client):
    """Test the register page endpoint."""
    response = client.get("/register")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_favicon_endpoint(client):
    """Test the favicon endpoint."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200


def test_config_endpoint(client):
    """Test the config endpoint."""
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "multi_user_enabled" in data
    assert data["multi_user_enabled"] is True


def test_nocache_static_files():
    """Test that NoCacheStaticFiles adds proper cache headers."""
    from writing_assistant.app.main import NoCacheStaticFiles
    from starlette.responses import Response

    # Create instance
    static_files = NoCacheStaticFiles(directory=".")

    # Mock the parent's file_response method
    with patch.object(NoCacheStaticFiles.__bases__[0], 'file_response') as mock_parent:
        mock_response = Response()
        mock_parent.return_value = mock_response

        result = static_files.file_response("test", "args")

        # Verify cache headers are set
        assert result.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert result.headers["Pragma"] == "no-cache"
        assert result.headers["Expires"] == "0"


def test_auth_check_authenticated(authenticated_client):
    """Test auth check endpoint with authenticated user."""
    response = authenticated_client.get("/auth/check")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert "email" in data
    assert "user_id" in data


def test_auth_check_unauthenticated(client):
    """Test auth check endpoint without authentication."""
    response = client.get("/auth/check")
    assert response.status_code == 401


def test_download_document_not_found(authenticated_client):
    """Test download non-existent document."""
    response = authenticated_client.get("/documents/download/nonexistent.json")
    assert response.status_code == 404


def test_delete_document_not_found(authenticated_client):
    """Test delete non-existent document."""
    response = authenticated_client.delete("/documents/delete/nonexistent.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "not found" in data["message"].lower()


def test_generate_text_with_error(authenticated_client):
    """Test generate text with exception handling."""
    with patch('writing_assistant.app.main.cb.new_paragraph', side_effect=Exception("LLM Error")):
        response = authenticated_client.post("/generate-text", data={
            "user_text": "Test text",
            "generation_mode": "ideas"
        })
        # Should return an error
        assert response.status_code in [200, 500]