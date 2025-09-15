"""Tests for the API endpoints."""

import pytest
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


def test_sections_crud(client):
    """Test basic CRUD operations for sections."""
    # Create a section
    response = client.post("/sections")
    assert response.status_code == 200
    section_data = response.json()
    assert "id" in section_data
    section_id = section_data["id"]

    # Update the section
    response = client.put(f"/sections/{section_id}", data={
        "main_point": "Test main point",
        "user_text": "Test user text"
    })
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["main_point"] == "Test main point"
    assert updated_data["user_text"] == "Test user text"

    # Delete the section
    response = client.delete(f"/sections/{section_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_document_operations(client):
    """Test document save/load operations."""
    # Create a test document by updating title and adding sections
    client.post("/title", data={"title": "Test Document"})
    response = client.post("/sections")
    section_id = response.json()["id"]
    client.put(f"/sections/{section_id}", data={
        "main_point": "Introduction",
        "user_text": "This is a test document."
    })

    # Save the document
    response = client.post("/documents/save", data={"filename": "test_doc"})
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
    response = client.post(f"/documents/load/{filename}")
    assert response.status_code == 200
    load_data = response.json()
    assert load_data["status"] == "success"
    assert load_data["title"] == "Test Document"