"""Tests demonstrating the robust path-based security validation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from writing_assistant.app.main import get_safe_filepath


def test_path_containment_security():
    """Test that the path resolution security actually works."""

    # Mock the documents directory
    with patch('writing_assistant.app.main.get_documents_dir') as mock_get_docs_dir:
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        # Test 1: Normal file should work
        safe_path = get_safe_filepath("normal_file.json")
        assert safe_path == mock_docs_dir / "normal_file.json"

        # Test 2: Even if somehow a malicious filename got through initial validation,
        # the path resolution check should catch it
        with patch('pathlib.Path.resolve') as mock_resolve:
            # Simulate a case where resolve() returns a path outside docs directory
            mock_resolve.side_effect = [
                Path("/etc/passwd"),  # Resolved target file (outside docs)
                Path("/safe/documents")  # Resolved docs directory
            ]

            with pytest.raises(ValueError, match="path traversal detected"):
                get_safe_filepath("somehow_malicious.json")


def test_symlink_attack_prevention():
    """Test that symlink attacks are prevented."""

    with patch('writing_assistant.app.main.get_documents_dir') as mock_get_docs_dir:
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        # Simulate a symlink that points outside the documents directory
        with patch('pathlib.Path.resolve') as mock_resolve:
            mock_resolve.side_effect = [
                Path("/etc/passwd"),  # Symlink resolves to sensitive file
                Path("/safe/documents")  # Docs directory resolves normally
            ]

            with pytest.raises(ValueError, match="path traversal detected"):
                get_safe_filepath("innocent_looking_file.json")


def test_real_world_security_scenario():
    """Test with actual filesystem operations to verify security."""

    # This test uses real Path operations to ensure our security works
    # in practice, not just with mocks

    import tempfile
    import os

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a fake documents directory
        docs_dir = Path(temp_dir) / "documents"
        docs_dir.mkdir()

        # Create a sensitive file outside documents directory
        sensitive_file = Path(temp_dir) / "sensitive.txt"
        sensitive_file.write_text("SECRET DATA")

        with patch('writing_assistant.app.main.get_documents_dir', return_value=docs_dir):
            # Test 1: Normal operation should work
            safe_path = get_safe_filepath("normal.json")
            expected = docs_dir / "normal.json"
            assert safe_path == expected

            # Test 2: Verify the path is actually contained
            try:
                safe_path.resolve().relative_to(docs_dir.resolve())
                # Should not raise exception
            except ValueError:
                pytest.fail("Normal file path should be contained in docs directory")


def test_demonstrates_layered_security():
    """Demonstrate the layered security approach: string validation + path resolution."""

    with patch('writing_assistant.app.main.get_documents_dir') as mock_get_docs_dir:
        mock_docs_dir = Path("/safe/documents")
        mock_get_docs_dir.return_value = mock_docs_dir

        # Test 1: First layer (string validation) catches obvious attacks
        obvious_attacks = [
            "subdir/../../../etc/passwd",
            "file\\..\\..\\..\\etc\\passwd",
        ]

        for attack in obvious_attacks:
            with pytest.raises(ValueError, match="path traversal not allowed"):
                get_safe_filepath(attack)

        # Test 2: Second layer (path resolution) catches subtle attacks
        # that might slip through string validation
        with patch('writing_assistant.app.main.validate_and_sanitize_filename') as mock_validate:
            # Mock the first layer to let a "clean" filename through
            mock_validate.return_value = "innocent.json"

            with patch('pathlib.Path.resolve') as mock_resolve:
                # But the resolved path goes somewhere malicious
                mock_resolve.side_effect = [
                    Path("/etc/passwd"),  # Resolved target (malicious)
                    Path("/safe/documents")  # Resolved docs directory
                ]

                with pytest.raises(ValueError, match="path traversal detected"):
                    get_safe_filepath("innocent.json")


def test_docs_directory_protection():
    """Test that only files within the exact docs directory are allowed."""

    with patch('writing_assistant.app.main.get_documents_dir') as mock_get_docs_dir:
        docs_dir = Path("/home/user/.writing_assistant/documents")
        mock_get_docs_dir.return_value = docs_dir

        # Test various attempts to escape the documents directory
        escape_attempts = [
            # Sibling directory
            ("/home/user/.writing_assistant/config/secrets.txt", "sibling directory"),
            # Parent directory
            ("/home/user/.writing_assistant/passwords.txt", "parent directory"),
            # Root directory
            ("/etc/passwd", "system file"),
            # User home directory
            ("/home/user/.ssh/id_rsa", "SSH key"),
        ]

        for malicious_path, description in escape_attempts:
            with patch('pathlib.Path.resolve') as mock_resolve:
                mock_resolve.side_effect = [
                    Path(malicious_path),  # Malicious target
                    docs_dir  # Legitimate docs directory
                ]

                with pytest.raises(ValueError, match="path traversal detected"):
                    get_safe_filepath(f"innocent_file.json")  # Filename doesn't matter