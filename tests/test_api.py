"""Tests for the API endpoints."""

import pytest
import json
from fastapi.testclient import TestClient


def test_root_endpoint(client):
    """Test the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_metadata_get(client):
    """Test getting metadata."""
    response = client.get("/metadata")
    assert response.status_code == 200
    data = response.json()
    assert "writing_style" in data
    assert "target_audience" in data
    assert "tone" in data


def test_metadata_post(client):
    """Test updating metadata."""
    response = client.post("/metadata", data={
        "writing_style": "casual",
        "target_audience": "students",
        "tone": "friendly"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify the change was applied
    response = client.get("/metadata")
    data = response.json()
    assert data["writing_style"] == "casual"
    assert data["target_audience"] == "students"
    assert data["tone"] == "friendly"


def test_generate_text(client):
    """Test text generation endpoint."""
    response = client.post("/generate-text", data={
        "main_point": "Introduction to AI",
        "user_text": "AI is changing the world",
        "title": "AI Overview",
        "generation_mode": "ideas"
    })
    assert response.status_code == 200
    data = response.json()
    assert "generated_text" in data
    assert isinstance(data["generated_text"], str)


def test_document_save_and_load(client):
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
    response = client.post("/documents/save", data={
        "filename": "test_doc",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    save_data = response.json()
    assert save_data["status"] == "success"
    filename = save_data["filename"]

    # List documents
    response = client.get("/documents/list")
    assert response.status_code == 200
    files = response.json()["files"]
    assert len(files) > 0
    assert any(f["filename"] == filename for f in files)

    # Load the document
    response = client.get(f"/documents/load/{filename}")
    assert response.status_code == 200
    load_data = response.json()
    assert load_data["status"] == "success"
    assert load_data["document"]["title"] == "Test Document"
    assert load_data["document"]["content"] == test_document["content"]


def test_document_save_as(client):
    """Test save-as functionality."""
    test_document = {
        "title": "Save As Test",
        "content": "Testing save as functionality",
        "sections": [],
        "created_at": "2024-01-01T00:00:00Z"
    }

    response = client.post("/documents/save-as", data={
        "filename": "save_as_test",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "save_as_test.json"


def test_document_delete(client):
    """Test document deletion."""
    # First create a document to delete
    test_document = {
        "title": "Delete Test",
        "content": "This will be deleted",
        "sections": []
    }

    # Save the document
    response = client.post("/documents/save", data={
        "filename": "delete_test",
        "document_data": json.dumps(test_document)
    })
    assert response.status_code == 200
    filename = response.json()["filename"]

    # Delete the document
    response = client.delete(f"/documents/delete/{filename}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify it's gone
    response = client.get(f"/documents/load/{filename}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"