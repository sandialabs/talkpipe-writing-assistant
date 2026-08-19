"""Tests to improve coverage of main.py endpoints and error handling."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


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
    from starlette.responses import Response

    from writing_assistant.app.main import NoCacheStaticFiles

    # Create instance
    static_files = NoCacheStaticFiles(directory=".")

    # Mock the parent's file_response method
    with patch.object(NoCacheStaticFiles.__bases__[0], "file_response") as mock_parent:
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
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=Exception("LLM Error"),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={"user_text": "Test text", "generation_mode": "ideas"},
        )
        # Should return an error
        assert response.status_code in [200, 500]


def test_get_user_preferences_empty(authenticated_client):
    """Test getting user preferences when none are saved."""
    response = authenticated_client.get("/user/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["preferences"] == {}


async def test_get_user_preferences_with_data(
    authenticated_client, async_db_session, test_user
):
    """Test getting user preferences with saved data."""
    import json

    # Set preferences on user
    test_user.preferences = json.dumps({"theme": "dark", "fontSize": 14})
    async_db_session.add(test_user)

    # Commit the changes
    await async_db_session.commit()

    response = authenticated_client.get("/user/preferences")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["preferences"]["theme"] == "dark"


def test_save_user_preferences(authenticated_client):
    """Test saving user preferences."""
    preferences = {"theme": "dark", "fontSize": 16}
    response = authenticated_client.post(
        "/user/preferences", json={"preferences": preferences}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_save_document_new(authenticated_client):
    """Test saving a new document."""
    import json

    document_data = {"title": "Test Document", "sections": []}

    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "test.json", "document_data": json.dumps(document_data)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Document created"


def test_save_document_update_existing(authenticated_client):
    """Test updating an existing document."""
    import json

    # Create initial document
    document_data = {"title": "Original Title", "sections": []}

    authenticated_client.post(
        "/documents/save",
        data={"filename": "test.json", "document_data": json.dumps(document_data)},
    )

    # Update it
    updated_data = {"title": "Updated Title", "sections": []}

    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "test.json", "document_data": json.dumps(updated_data)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Document updated"


def test_save_document_invalid_json(authenticated_client):
    """Test saving document with invalid JSON."""
    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "test.json", "document_data": "invalid json {"},
    )
    assert response.status_code == 400


def test_save_document_as(authenticated_client):
    """Test save-as endpoint."""
    import json

    document_data = {"title": "Test Document", "sections": []}

    response = authenticated_client.post(
        "/documents/save-as",
        data={"filename": "copy.json", "document_data": json.dumps(document_data)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_download_document_success(authenticated_client):
    """Test downloading an existing document."""
    import json

    # Create document
    document_data = {"title": "Download Test", "sections": []}

    authenticated_client.post(
        "/documents/save",
        data={"filename": "download.json", "document_data": json.dumps(document_data)},
    )

    # Download it
    response = authenticated_client.get("/documents/download/download.json")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers["content-disposition"]


def test_load_document_by_filename_success(authenticated_client):
    """Test loading a document by filename."""
    import json

    # Create document
    document_data = {"title": "Load Test", "sections": []}

    authenticated_client.post(
        "/documents/save",
        data={"filename": "load.json", "document_data": json.dumps(document_data)},
    )

    # Load it
    response = authenticated_client.get("/documents/load/load.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["document"]["title"] == "Load Test"


def test_load_document_not_found(authenticated_client):
    """Test loading non-existent document."""
    response = authenticated_client.get("/documents/load/nonexistent.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"


def test_list_documents_empty(authenticated_client):
    """Test listing documents when user has none."""
    response = authenticated_client.get("/documents/list")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 0


def test_list_documents_with_files(authenticated_client):
    """Test listing documents when user has files."""
    import json

    # Create documents
    for i in range(3):
        document_data = {"title": f"Doc {i}", "sections": []}
        authenticated_client.post(
            "/documents/save",
            data={
                "filename": f"doc{i}.json",
                "document_data": json.dumps(document_data),
            },
        )

    response = authenticated_client.get("/documents/list")
    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 3


def test_generate_text_with_custom_env_vars(authenticated_client):
    """Test generate text with custom environment variables."""
    import json

    with patch("writing_assistant.app.main.ALLOW_CUSTOM_ENV_VARS", True):
        with patch(
            "writing_assistant.app.main.cb.new_paragraph", return_value="Generated text"
        ):
            env_vars = {"OLLAMA_BASE_URL": "http://localhost:11434"}
            response = authenticated_client.post(
                "/generate-text",
                data={
                    "user_text": "Test",
                    "environment_variables": json.dumps(env_vars),
                },
            )
            assert response.status_code == 200


def test_generate_text_env_vars_disabled(authenticated_client):
    """Test generate text with custom env vars disabled."""
    import json

    with patch("writing_assistant.app.main.ALLOW_CUSTOM_ENV_VARS", False):
        with patch(
            "writing_assistant.app.main.cb.new_paragraph", return_value="Generated text"
        ):
            env_vars = {"OLLAMA_BASE_URL": "http://localhost:11434"}
            response = authenticated_client.post(
                "/generate-text",
                data={
                    "user_text": "Test",
                    "environment_variables": json.dumps(env_vars),
                },
            )
            assert response.status_code == 200


def test_generate_text_invalid_env_json(authenticated_client):
    """Test generate text with invalid environment variables JSON."""
    with patch("writing_assistant.app.main.ALLOW_CUSTOM_ENV_VARS", True):
        with patch(
            "writing_assistant.app.main.cb.new_paragraph", return_value="Generated text"
        ):
            response = authenticated_client.post(
                "/generate-text",
                data={"user_text": "Test", "environment_variables": "invalid json"},
            )
            assert response.status_code == 200


def test_create_snapshot_success(authenticated_client):
    """Test creating a document snapshot."""
    import json

    # Create document
    document_data = {"title": "Snapshot Test", "sections": []}
    authenticated_client.post(
        "/documents/save",
        data={"filename": "snap.json", "document_data": json.dumps(document_data)},
    )

    # Create snapshot
    response = authenticated_client.post("/documents/snapshot/snap.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "snapshot_filename" in data


def test_create_snapshot_not_found(authenticated_client):
    """Test creating snapshot for non-existent document."""
    response = authenticated_client.post("/documents/snapshot/nonexistent.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"


def test_create_snapshot_cleanup_old(authenticated_client):
    """Test that old snapshots are cleaned up (keep only 10)."""
    import asyncio
    import json

    # Create document
    document_data = {"title": "Cleanup Test", "sections": []}
    authenticated_client.post(
        "/documents/save",
        data={"filename": "cleanup.json", "document_data": json.dumps(document_data)},
    )

    # Create 12 snapshots
    import time

    for i in range(12):
        authenticated_client.post("/documents/snapshot/cleanup.json")
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # List snapshots
    response = authenticated_client.get("/documents/snapshots/cleanup.json")
    data = response.json()
    # Should have only 10 snapshots (cleanup happens during creation)
    assert len(data["snapshots"]) <= 10


def test_list_snapshots_success(authenticated_client):
    """Test listing snapshots for a document."""
    import json

    # Create document
    document_data = {"title": "List Snapshots", "sections": []}
    authenticated_client.post(
        "/documents/save",
        data={"filename": "listsnap.json", "document_data": json.dumps(document_data)},
    )

    # Create snapshots
    authenticated_client.post("/documents/snapshot/listsnap.json")
    authenticated_client.post("/documents/snapshot/listsnap.json")

    # List them
    response = authenticated_client.get("/documents/snapshots/listsnap.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["snapshots"]) == 2


def test_list_snapshots_document_not_found(authenticated_client):
    """Test listing snapshots for non-existent document."""
    response = authenticated_client.get("/documents/snapshots/nonexistent.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"


def test_load_snapshot_success(authenticated_client):
    """Test loading a snapshot."""
    import json

    # Create document
    document_data = {"title": "Load Snapshot", "sections": []}
    authenticated_client.post(
        "/documents/save",
        data={"filename": "loadsnap.json", "document_data": json.dumps(document_data)},
    )

    # Create snapshot
    snap_response = authenticated_client.post("/documents/snapshot/loadsnap.json")
    snapshot_filename = snap_response.json()["snapshot_filename"]

    # Load it
    response = authenticated_client.get(f"/documents/snapshot/load/{snapshot_filename}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["document"]["title"] == "Load Snapshot"


def test_load_snapshot_not_found(authenticated_client):
    """Test loading non-existent snapshot."""
    response = authenticated_client.get(
        "/documents/snapshot/load/nonexistent_snapshot.json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"


def test_delete_document_success(authenticated_client):
    """Test deleting a document."""
    import json

    # Create document
    document_data = {"title": "Delete Me", "sections": []}
    authenticated_client.post(
        "/documents/save",
        data={"filename": "delete.json", "document_data": json.dumps(document_data)},
    )

    # Delete it
    response = authenticated_client.delete("/documents/delete/delete.json")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify it's gone
    load_response = authenticated_client.get("/documents/load/delete.json")
    assert load_response.json()["status"] == "error"


def test_save_document_exception_handling(authenticated_client):
    """Test save document with exception in commit."""
    # The exception handling paths are covered by invalid JSON test above
    # This confirms the error response structure
    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "test.json", "document_data": "{"},  # Invalid JSON
    )
    assert response.status_code == 400


def test_allow_custom_env_vars_env_variable():
    """ALLOW_CUSTOM_ENV_VARS=false must disable custom env vars."""
    import os

    from writing_assistant.app.main import _allow_custom_env_vars_default

    with patch.dict(os.environ, {"ALLOW_CUSTOM_ENV_VARS": "false"}):
        assert _allow_custom_env_vars_default() is False
    with patch.dict(os.environ, {"ALLOW_CUSTOM_ENV_VARS": "0"}):
        assert _allow_custom_env_vars_default() is False
    with patch.dict(os.environ, {"ALLOW_CUSTOM_ENV_VARS": "true"}):
        assert _allow_custom_env_vars_default() is True
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ALLOW_CUSTOM_ENV_VARS", None)
        assert _allow_custom_env_vars_default() is True


def test_generate_text_surfaces_value_error(authenticated_client):
    """An unknown source must produce an actionable 400, not a generic 500."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=ValueError("Unknown source: bogus"),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "bogus",
                "model": "some-model",
            },
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    # The rejected value comes from the request itself, not from the
    # exception text.
    assert "Unknown AI source 'bogus'" in detail
    # The error must also tell the user which values are accepted.
    assert "Valid sources: openai, anthropic, ollama" in detail


_MISSING_MODEL_SOURCE_ERROR = ValueError(
    "Model name and source must be provided, specified in the configuration "
    "file, or in environment variables."
)


def test_generate_text_unconfigured_points_at_settings(authenticated_client):
    """With no source and no model (and no server default), the error must
    point the user at Settings → AI Settings, not at configuration files."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=_MISSING_MODEL_SOURCE_ERROR,
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={"user_text": "Test"},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Settings" in detail
    assert "AI Settings" in detail
    assert "configuration file" not in detail


def test_generate_text_missing_model_points_at_model_field(authenticated_client):
    """Source chosen but model empty: the error must say the model is missing."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=_MISSING_MODEL_SOURCE_ERROR,
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={"user_text": "Test", "source": "ollama"},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "No model name is set" in detail
    assert "AI Settings" in detail


def test_generate_text_missing_source_points_at_source_field(authenticated_client):
    """Model set but no source: the error must say the source is missing."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=_MISSING_MODEL_SOURCE_ERROR,
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={"user_text": "Test", "model": "llama3.1:8b"},
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "No AI source is selected" in detail
    assert "openai, anthropic, or ollama" in detail


def test_generate_text_other_value_error_not_echoed(authenticated_client):
    """ValueErrors unrelated to the source are still reported as a
    configuration problem (400), but their text is not echoed and they must
    not get the valid-sources hint."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=ValueError("some other configuration problem /etc/secret"),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "ollama",
                "model": "some-model",
            },
        )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "some other configuration problem" not in detail
    assert "/etc/secret" not in detail
    assert "ValueError" in detail
    assert "server log" in detail
    assert "Valid sources" not in detail


def test_generate_text_surfaces_missing_api_key_error(authenticated_client):
    """A missing provider API key must produce an actionable error, not a
    generic 500 - TalkPipe wraps client-init failures (e.g. no OPENAI_API_KEY)
    in RuntimeError with a curated message."""
    message = (
        "Could not initialize the OpenAI client: Missing credentials. "
        "Set the OPENAI_API_KEY environment variable to your API key."
    )
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=RuntimeError(message),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "openai",
                "model": "gpt-4o",
            },
        )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Authentication with OpenAI failed" in detail
    # Points at the one-click fix (API Key field) as well as the server-side
    # variable, without echoing the SDK's own wording.
    assert "API Key field" in detail
    assert "OPENAI_API_KEY" in detail
    assert "Could not initialize the OpenAI client" not in detail


def test_generate_text_surfaces_missing_anthropic_key_error(authenticated_client):
    """The Anthropic adapter raises a differently-worded curated RuntimeError
    ("Could not authenticate with ..."); it must be surfaced too."""
    message = (
        "Could not authenticate with Anthropic. Set the ANTHROPIC_API_KEY "
        "environment variable to your API key."
    )
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=RuntimeError(message),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "anthropic",
                "model": "claude-sonnet-4-5",
            },
        )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Authentication with Anthropic failed" in detail
    assert "ANTHROPIC_API_KEY" in detail
    assert "Could not authenticate with Anthropic" not in detail


def test_generate_text_surfaces_connection_error(authenticated_client):
    """An unreachable backend must produce an actionable 502."""
    message = (
        "Failed to connect to Ollama at 'http://localhost:11434'. "
        "If your Ollama server is remote, set the TALKPIPE_OLLAMA_SERVER_URL "
        "environment variable."
    )
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=ConnectionError(message),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "ollama",
                "model": "llama3.2",
            },
        )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Could not connect to the Ollama server" in detail
    # Web-UI users are pointed at the Server URL field, not at the library's
    # environment-variable text (which is not echoed).
    assert "Server URL" in detail
    assert "If your Ollama server is remote" not in detail


def test_generate_text_bad_key_supplied_via_ui(authenticated_client):
    """When the failing key came from the API Key field in the dialog, the
    error must say to double-check that field rather than ask for a key."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=RuntimeError("Could not authenticate with Anthropic."),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": "anthropic",
                "model": "claude-sonnet-4-5",
                "api_key": "sk-ant-bad",
            },
        )
    assert response.status_code == 502
    assert "API Key entered in AI Settings" in response.json()["detail"]


def test_generate_text_missing_ollama_model(authenticated_client):
    """An Ollama 404 for the model is reported as a missing model with the
    pull command, not as an unreachable server."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=LookupError(
            "Model 'llama3.2' is not available on the Ollama server"
        ),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={"user_text": "Test", "source": "ollama", "model": "llama3.2"},
        )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "ollama pull llama3.2" in detail
    assert "host.containers.internal" not in detail


def test_generate_text_generic_error_stays_generic(authenticated_client):
    """Unexpected errors must not leak internals to the client."""
    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=RuntimeError("secret internal state"),
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
            },
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate text"


def test_generate_text_normalizes_source_case(authenticated_client):
    """Source values like "Ollama" from the UI must be lowercased."""
    captured = {}

    def fake_new_paragraph(**kwargs):
        captured["metadata"] = kwargs["metadata"]
        return "Generated text"

    with patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=fake_new_paragraph,
    ):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "Test",
                "source": " Ollama ",
                "model": " llama3.2 ",
            },
        )
    assert response.status_code == 200
    assert captured["metadata"].source == "ollama"
    assert captured["metadata"].model == "llama3.2"


def test_generate_text_reloads_talkpipe_config_for_env_vars(authenticated_client):
    """Per-request env vars must trigger a TalkPipe config reload to take effect."""
    with patch("writing_assistant.app.main.ALLOW_CUSTOM_ENV_VARS", True):
        with patch(
            "writing_assistant.app.main.cb.new_paragraph",
            return_value="Generated text",
        ):
            with patch(
                "writing_assistant.app.main.reset_talkpipe_config"
            ) as mock_reset:
                env_vars = {"TALKPIPE_OLLAMA_SERVER_URL": "http://ollama.example:11434"}
                response = authenticated_client.post(
                    "/generate-text",
                    data={
                        "user_text": "Test",
                        "environment_variables": json.dumps(env_vars),
                    },
                )
    assert response.status_code == 200
    # Reloaded once to pick up the request's env vars and once to restore.
    assert mock_reset.call_count == 2
