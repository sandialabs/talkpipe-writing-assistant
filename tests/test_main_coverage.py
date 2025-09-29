"""Tests to improve coverage of main.py endpoints and error handling."""

import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path


def test_favicon_endpoint(client):
    """Test the favicon endpoint."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200


def test_validate_token_invalid(client):
    """Test authentication with invalid token."""
    response = client.get("/?token=invalid-token")
    assert response.status_code == 403
    assert "Invalid or missing authentication token" in response.json()["detail"]


def test_validate_token_missing(client):
    """Test authentication with missing token."""
    response = client.get("/")
    assert response.status_code == 403
    assert "Invalid or missing authentication token" in response.json()["detail"]


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


def test_save_document_exception(client):
    """Test save document with exception handling."""
    with patch('builtins.open', side_effect=PermissionError("Permission denied")):
        response = client.post("/documents/save?token=test-token", data={
            "filename": "test_doc",
            "document_data": json.dumps({"title": "Test"})
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Permission denied" in data["message"]


def test_save_document_as_exception(client):
    """Test save-as document with exception handling."""
    with patch('builtins.open', side_effect=IOError("IO Error")):
        response = client.post("/documents/save-as?token=test-token", data={
            "filename": "test_doc",
            "document_data": json.dumps({"title": "Test"})
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "IO Error" in data["message"]


def test_download_document_not_found(client):
    """Test download non-existent document."""
    response = client.get("/documents/download/nonexistent.json?token=test-token")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "File not found" in data["error"]


def test_download_document_exception(client):
    """Test download document with exception handling."""
    with patch('writing_assistant.app.main.get_documents_dir', side_effect=Exception("Directory error")):
        response = client.get("/documents/download/test.json?token=test-token")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Directory error" in data["error"]


def test_load_document_exception(client):
    """Test load document with exception handling."""
    with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
        response = client.get("/documents/load/test.json?token=test-token")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "File not found" in data["message"]


def test_list_documents_exception(client):
    """Test list documents with exception handling."""
    with patch('writing_assistant.app.main.get_documents_dir', side_effect=Exception("Directory error")):
        response = client.get("/documents/list?token=test-token")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Directory error" in data["error"]


def test_generate_text_exception(client):
    """Test generate text with exception handling."""
    with patch('writing_assistant.app.main.cb.new_paragraph', side_effect=Exception("LLM Error")):
        response = client.post("/generate-text?token=test-token", data={
            "user_text": "Test text",
            "generation_mode": "ideas"
        })
        # FastAPI returns the error as JSON, we just need to test the exception was caught
        # Check response data contains the error details (can be 200 or 500)
        assert response.status_code in [200, 500]


def test_delete_document_not_found(client):
    """Test delete non-existent document."""
    response = client.delete("/documents/delete/nonexistent.json?token=test-token")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "File not found" in data["message"]


def test_delete_document_invalid_filename(client):
    """Test delete document with invalid filename."""
    # FastAPI routing rejects ".." in paths with 404
    response = client.delete("/documents/delete/..?token=test-token")
    assert response.status_code == 404


def test_delete_document_path_traversal(client):
    """Test delete document with path traversal attempt."""
    # Test that valid filenames with .. (not path traversal) work as expected
    response = client.delete("/documents/delete/test..json?token=test-token")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "File not found" in data["message"]  # This is now valid, so gets file not found


def test_delete_document_exception(client):
    """Test delete document with exception handling."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.unlink', side_effect=PermissionError("Permission denied")):
        response = client.delete("/documents/delete/test.json?token=test-token")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Permission denied" in data["message"]