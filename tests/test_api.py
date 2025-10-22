"""Tests for the API endpoints."""

import json
from unittest.mock import patch


def test_root_endpoint(client):
    """Test the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# NOTE: Metadata endpoints don't exist in the current implementation
# Metadata is passed with each request rather than stored server-side

# def test_metadata_get(client):
#     """Test getting metadata."""
#     response = client.get("/metadata?token=test-token")
#     assert response.status_code == 200
#     data = response.json()
#     assert "writing_style" in data
#     assert "target_audience" in data
#     assert "tone" in data


# def test_metadata_post(client):
#     """Test updating metadata."""
#     response = client.post("/metadata?token=test-token", data={
#         "writing_style": "casual",
#         "target_audience": "students",
#         "tone": "friendly"
#     })
#     assert response.status_code == 200
#     assert response.json()["status"] == "success"

#     # Verify the change was applied
#     response = client.get("/metadata?token=test-token")
#     data = response.json()
#     assert data["writing_style"] == "casual"
#     assert data["target_audience"] == "students"
#     assert data["tone"] == "friendly"


@patch('writing_assistant.app.main.cb.new_paragraph')
def test_generate_text(mock_new_paragraph, authenticated_client):
    """Test text generation endpoint."""
    # Mock the text generation to return a test string
    mock_new_paragraph.return_value = "This is generated text about AI changing the world."

    response = authenticated_client.post("/generate-text", data={
        "user_text": "AI is changing the world",
        "title": "AI Overview",
        "generation_mode": "ideas"
    })
    assert response.status_code == 200
    data = response.json()
    assert "generated_text" in data
    assert isinstance(data["generated_text"], str)
    assert data["generated_text"] == "This is generated text about AI changing the world."

    # Verify the mock was called
    mock_new_paragraph.assert_called_once()


def test_document_save_and_load(authenticated_client):
    """Test document save/load operations with browser-provided data."""
    # Create test document data (simulating browser state)
    test_document = {
        "title": "Test Document",
        "content": "This is a test document.\n\nThis is another paragraph.",
        "sections": [
            {
                "id": "section-1",
                "text": "This is a test document.",
                "generated_text": "AI-generated expansion of the first section"
            },
            {
                "id": "section-2",
                "text": "This is another paragraph.",
                "generated_text": "AI-generated expansion of the second section"
            }
        ],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

    # Save the document
    response = authenticated_client.post("/documents/save", data={
        "filename": "test_doc",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    save_data = response.json()
    assert save_data["status"] == "success"
    filename = save_data["filename"]

    # List documents
    response = authenticated_client.get("/documents/list")
    assert response.status_code == 200
    files = response.json()["files"]
    assert len(files) > 0
    assert any(f["filename"] == filename for f in files)

    # Load the document
    response = authenticated_client.get(f"/documents/load/{filename}")
    assert response.status_code == 200
    load_data = response.json()
    assert load_data["status"] == "success"
    assert load_data["document"]["title"] == "Test Document"
    assert load_data["document"]["content"] == test_document["content"]


def test_document_save_as(authenticated_client):
    """Test save-as functionality."""
    test_document = {
        "title": "Save As Test",
        "content": "Testing save as functionality",
        "sections": [],
        "created_at": "2024-01-01T00:00:00Z"
    }

    response = authenticated_client.post("/documents/save-as", data={
        "filename": "save_as_test",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_document_delete(authenticated_client):
    """Test document deletion."""
    # First create a document to delete
    test_document = {
        "title": "Delete Test",
        "content": "This will be deleted",
        "sections": []
    }

    # Save the document
    response = authenticated_client.post("/documents/save", data={
        "filename": "delete_test",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    filename = response.json()["filename"]

    # Delete the document
    response = authenticated_client.delete(f"/documents/delete/{filename}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify it's gone
    response = authenticated_client.get(f"/documents/load/{filename}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"