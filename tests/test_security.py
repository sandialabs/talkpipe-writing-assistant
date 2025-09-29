"""Tests for filename security validation functions."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from writing_assistant.app.main import validate_and_sanitize_filename, get_safe_filepath


class TestFilenameValidation:
    """Test cases for filename validation and sanitization."""

    def test_valid_filename(self):
        """Test that valid filenames are accepted."""
        result = validate_and_sanitize_filename("test_document.json")
        assert result == "test_document.json"

    def test_filename_without_extension(self):
        """Test that .json extension is added automatically."""
        result = validate_and_sanitize_filename("test_document")
        assert result == "test_document.json"

    def test_sanitize_special_characters(self):
        """Test that special characters are removed."""
        result = validate_and_sanitize_filename("test@#$%document")
        assert result == "testdocument.json"

    def test_preserve_allowed_characters(self):
        """Test that allowed characters are preserved."""
        result = validate_and_sanitize_filename("test-document_v1.0")
        assert result == "test-document_v1.0.json"

    def test_path_traversal_dotdot(self):
        """Test that path traversal with .. is rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            validate_and_sanitize_filename("../secret.json")

    def test_path_traversal_dotdot_middle(self):
        """Test that .. in middle of filename is allowed (not path traversal)."""
        # This should be allowed since test..json is not path traversal
        result = validate_and_sanitize_filename("test..json")
        assert result == "test..json"

    def test_hidden_files(self):
        """Test that hidden files (starting with .) are rejected."""
        with pytest.raises(ValueError, match="absolute paths not allowed"):
            validate_and_sanitize_filename(".hidden_file.json")

    def test_absolute_path_unix(self):
        """Test that absolute Unix paths are rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            validate_and_sanitize_filename("/etc/passwd")

    def test_drive_letters_windows(self):
        """Test that Windows drive letters are rejected."""
        with pytest.raises(ValueError, match="path traversal not allowed"):
            validate_and_sanitize_filename("C:\\Windows\\system32\\config")

    def test_empty_filename(self):
        """Test that empty filenames are rejected."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            validate_and_sanitize_filename("")

    def test_whitespace_only_filename(self):
        """Test that whitespace-only filenames are rejected."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            validate_and_sanitize_filename("   ")

    def test_filename_becomes_empty_after_sanitization(self):
        """Test that filenames with no valid characters are rejected."""
        with pytest.raises(ValueError, match="no valid characters remaining"):
            validate_and_sanitize_filename("@#$%^&*()")

    def test_filename_too_long(self):
        """Test that excessively long filenames are rejected."""
        long_name = "a" * 300
        with pytest.raises(ValueError, match="Filename too long"):
            validate_and_sanitize_filename(long_name)

    def test_complex_path_traversal(self):
        """Test complex path traversal attempts."""
        malicious_filenames = [
            "../../etc/passwd",
            "..\\..\\Windows\\system32\\config",
            "test/../../../secret.json",
            "test\\..\\..\\secret.json",
        ]

        for filename in malicious_filenames:
            with pytest.raises(ValueError):
                validate_and_sanitize_filename(filename)

    def test_url_encoded_path_traversal(self):
        """Test URL-encoded path traversal attempts."""
        # The URL-encoded string "%2e%2e%2fsecret" would be decoded by FastAPI to "../secret"
        # Our validation function should reject the decoded version
        import urllib.parse
        decoded = urllib.parse.unquote("%2e%2e%2fsecret")
        with pytest.raises(ValueError):
            validate_and_sanitize_filename(decoded)


class TestSafeFilepath:
    """Test cases for get_safe_filepath function."""

    @patch('writing_assistant.app.main.get_documents_dir')
    def test_safe_filepath_normal(self, mock_get_docs_dir):
        """Test that normal filenames produce safe filepaths."""
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        result = get_safe_filepath("test_document.json")

        assert result == mock_docs_dir / "test_document.json"
        assert result.name == "test_document.json"

    @patch('writing_assistant.app.main.get_documents_dir')
    def test_safe_filepath_traversal_protection(self, mock_get_docs_dir):
        """Test that path traversal is prevented even after sanitization."""
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        # This should fail at the validation step
        with pytest.raises(ValueError, match="path traversal"):
            get_safe_filepath("../../../etc/passwd")

    @patch('writing_assistant.app.main.get_documents_dir')
    def test_safe_filepath_relative_to_check(self, mock_get_docs_dir):
        """Test that the relative_to check works."""
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        # Mock Path.resolve() to return a path outside documents dir
        with patch('pathlib.Path.resolve') as mock_resolve:
            # First call is for filepath.resolve()
            # Second call is for docs_dir.resolve()
            mock_resolve.side_effect = [
                Path("/dangerous/path/file.json"),  # Resolved filepath
                Path("/safe/documents")  # Resolved docs_dir
            ]

            with pytest.raises(ValueError, match="path traversal detected"):
                get_safe_filepath("test.json")


class TestSecurityIntegration:
    """Integration tests for security with API endpoints."""

    def test_save_document_with_malicious_filename(self, client):
        """Test that save endpoint rejects malicious filenames."""
        response = client.post("/documents/save?token=test-token", data={
            "filename": "../../../etc/passwd",
            "document_data": '{"title": "test"}'
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "Invalid filename" in data["message"]

    def test_load_document_with_malicious_filename(self, client):
        """Test that FastAPI routing rejects path traversal in URLs."""
        # FastAPI should reject this at the routing level with 404
        response = client.get("/documents/load/../secret.json?token=test-token")
        assert response.status_code == 404

    def test_download_document_with_malicious_filename(self, client):
        """Test that FastAPI routing rejects path traversal in URLs."""
        # FastAPI should reject this at the routing level with 404
        response = client.get("/documents/download/../secret.json?token=test-token")
        assert response.status_code == 404

    def test_delete_document_with_malicious_filename(self, client):
        """Test that FastAPI routing rejects path traversal in URLs."""
        # FastAPI should reject this at the routing level with 404
        response = client.delete("/documents/delete/../secret.json?token=test-token")
        assert response.status_code == 404

    def test_windows_path_traversal_attempts(self, client):
        """Test Windows-style path traversal attempts."""
        malicious_paths = [
            "..\\..\\Windows\\system32\\config",
            "C:\\Windows\\system32\\hosts",
            "test\\..\\..\\secret.json"
        ]

        for path in malicious_paths:
            response = client.get(f"/documents/load/{path}?token=test-token")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "Invalid filename" in data["message"]

    def test_null_byte_injection(self, client):
        """Test null byte injection attempts."""
        # Null bytes should be filtered out during sanitization
        response = client.post("/documents/save?token=test-token", data={
            "filename": "test\x00.json",
            "document_data": '{"title": "test"}'
        })

        assert response.status_code == 200
        data = response.json()
        # Should either succeed with sanitized name or fail validation
        if data["status"] == "success":
            assert "\x00" not in data["filename"]
        else:
            assert "Invalid filename" in data["message"]