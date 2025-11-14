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


@patch('writing_assistant.app.main.cb.new_paragraph')
def test_generate_text_truncates_context_to_2000_chars(mock_new_paragraph, authenticated_client):
    """Test that prev/next paragraphs are truncated to 2000 characters."""
    # Mock the text generation
    mock_new_paragraph.return_value = "Generated text."

    # Create a paragraph with more than 2000 characters
    # Each "word{i}" is about 6-7 chars, so 400 words = ~2600 chars
    long_paragraph = " ".join([f"word{i}" for i in range(400)])

    response = authenticated_client.post("/generate-text", data={
        "user_text": "Current paragraph",
        "title": "Test Document",
        "prev_paragraph": long_paragraph,
        "next_paragraph": long_paragraph,
        "generation_mode": "rewrite"
    })

    assert response.status_code == 200

    # Verify the callback was called
    mock_new_paragraph.assert_called_once()

    # Get the actual arguments passed to the callback
    call_args = mock_new_paragraph.call_args
    prev_para = call_args.kwargs['prev_paragraph']
    next_para = call_args.kwargs['next_paragraph']

    # Verify they are truncated to 2000 characters
    assert len(prev_para) == 2000, f"Expected 2000 chars in prev_paragraph, got {len(prev_para)}"
    assert len(next_para) == 2000, f"Expected 2000 chars in next_paragraph, got {len(next_para)}"

    # Verify prev_paragraph gets the LAST 2000 characters
    assert prev_para == long_paragraph[-2000:]

    # Verify next_paragraph gets the FIRST 2000 characters
    assert next_para == long_paragraph[:2000]


@patch('writing_assistant.app.main.cb.new_paragraph')
def test_generate_text_includes_multiple_short_paragraphs(mock_new_paragraph, authenticated_client):
    """Test that multiple short paragraphs are included in context."""
    # Mock the text generation
    mock_new_paragraph.return_value = "Generated text."

    # Create multiple short paragraphs (each about 250 chars)
    # This simulates a realistic document with several short paragraphs
    paragraphs = [
        "This is paragraph 1. " * 10,  # ~250 chars
        "This is paragraph 2. " * 10,  # ~250 chars
        "This is paragraph 3. " * 10,  # ~250 chars
        "This is paragraph 4. " * 10,  # ~250 chars
        "This is paragraph 5. " * 10,  # ~250 chars
        "This is paragraph 6. " * 10,  # ~250 chars
        "This is paragraph 7. " * 10,  # ~250 chars
        "This is paragraph 8. " * 10,  # ~250 chars
    ]

    # Join them as they would be sent from the frontend (with \n\n separator)
    prev_context = "\n\n".join(paragraphs[:4])  # First 4 paragraphs before current
    next_context = "\n\n".join(paragraphs[4:])  # Last 4 paragraphs after current

    response = authenticated_client.post("/generate-text", data={
        "user_text": "Current paragraph being edited",
        "title": "Test Document",
        "prev_paragraph": prev_context,
        "next_paragraph": next_context,
        "generation_mode": "rewrite"
    })

    assert response.status_code == 200

    # Verify the callback was called
    mock_new_paragraph.assert_called_once()

    # Get the actual arguments passed to the callback
    call_args = mock_new_paragraph.call_args
    prev_para = call_args.kwargs['prev_paragraph']
    next_para = call_args.kwargs['next_paragraph']

    # Verify that multiple paragraphs are included
    # Since each paragraph is ~250 chars + 2 for \n\n separator,
    # we should get all 4 paragraphs (4 * 250 + 3 * 2 = ~1006 chars)
    assert "This is paragraph 1." in prev_para, "Should include paragraph 1"
    assert "This is paragraph 2." in prev_para, "Should include paragraph 2"
    assert "This is paragraph 3." in prev_para, "Should include paragraph 3"
    assert "This is paragraph 4." in prev_para, "Should include paragraph 4"

    assert "This is paragraph 5." in next_para, "Should include paragraph 5"
    assert "This is paragraph 6." in next_para, "Should include paragraph 6"
    assert "This is paragraph 7." in next_para, "Should include paragraph 7"
    assert "This is paragraph 8." in next_para, "Should include paragraph 8"

    # Verify the context is not truncated (since it's under 2000 chars)
    assert len(prev_para) < 2000, f"Should not be truncated, got {len(prev_para)} chars"
    assert len(next_para) < 2000, f"Should not be truncated, got {len(next_para)} chars"

    # Verify the exact content matches what we sent
    assert prev_para == prev_context
    assert next_para == next_context