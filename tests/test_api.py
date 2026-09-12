"""Tests for the API endpoints."""

import json
from unittest.mock import patch


def test_health_identifies_the_app_without_auth(client):
    """A second launch (or a desktop launcher) checks this to tell a running
    writing assistant from anything else on the port."""
    from writing_assistant import DIST_NAME, __version__

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"app": DIST_NAME, "version": __version__}


def test_root_endpoint(client):
    """Test the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_ai_source_is_a_dropdown_of_valid_values(client):
    """The AI Source field must be a select listing exactly the valid sources.

    A free-text input invited typos ("olama") that only failed at generation
    time; the dropdown makes invalid sources unrepresentable in the UI.
    """
    html = client.get("/").text
    assert '<select id="ai-source"' in html
    assert '<input type="text" id="ai-source"' not in html
    for value in ("openai", "anthropic", "ollama"):
        assert f'<option value="{value}"' in html
    # The empty value defers to the server's TalkPipe configuration, matching
    # the server-side default (Metadata.source == "").
    assert '<option value=""' in html


def test_login_page_returns_html(client):
    """Login page must render; wrong TemplateResponse args break Jinja2 cache."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_register_page_returns_html(client):
    """Register page must render; wrong TemplateResponse args break Jinja2 cache."""
    response = client.get("/register")
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


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text(mock_new_paragraph, authenticated_client):
    """Test text generation endpoint."""
    # Mock the text generation to return a test string
    mock_new_paragraph.return_value = (
        "This is generated text about AI changing the world."
    )

    response = authenticated_client.post(
        "/generate-text",
        data={
            "user_text": "AI is changing the world",
            "title": "AI Overview",
            "generation_mode": "ideas",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "generated_text" in data
    assert isinstance(data["generated_text"], str)
    assert (
        data["generated_text"] == "This is generated text about AI changing the world."
    )

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
                "generated_text": "AI-generated expansion of the first section",
            },
            {
                "id": "section-2",
                "text": "This is another paragraph.",
                "generated_text": "AI-generated expansion of the second section",
            },
        ],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

    # Save the document
    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "test_doc", "document_data": json.dumps(test_document)},
    )
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
        "created_at": "2024-01-01T00:00:00Z",
    }

    response = authenticated_client.post(
        "/documents/save-as",
        data={"filename": "save_as_test", "document_data": json.dumps(test_document)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_document_delete(authenticated_client):
    """Test document deletion."""
    # First create a document to delete
    test_document = {
        "title": "Delete Test",
        "content": "This will be deleted",
        "sections": [],
    }

    # Save the document
    response = authenticated_client.post(
        "/documents/save",
        data={"filename": "delete_test", "document_data": json.dumps(test_document)},
    )
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


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text_truncates_context_to_2000_chars(
    mock_new_paragraph, authenticated_client
):
    """Test that prev/next paragraphs are truncated to 2000 characters."""
    # Mock the text generation
    mock_new_paragraph.return_value = "Generated text."

    # Create a paragraph with more than 2000 characters
    # Each "word{i}" is about 6-7 chars, so 400 words = ~2600 chars
    long_paragraph = " ".join([f"word{i}" for i in range(400)])

    response = authenticated_client.post(
        "/generate-text",
        data={
            "user_text": "Current paragraph",
            "title": "Test Document",
            "prev_paragraph": long_paragraph,
            "next_paragraph": long_paragraph,
            "generation_mode": "rewrite",
        },
    )

    assert response.status_code == 200

    # Verify the callback was called
    mock_new_paragraph.assert_called_once()

    # Get the actual arguments passed to the callback
    call_args = mock_new_paragraph.call_args
    prev_para = call_args.kwargs["prev_paragraph"]
    next_para = call_args.kwargs["next_paragraph"]

    # Verify they are truncated to 2000 characters
    assert len(prev_para) == 2000, (
        f"Expected 2000 chars in prev_paragraph, got {len(prev_para)}"
    )
    assert len(next_para) == 2000, (
        f"Expected 2000 chars in next_paragraph, got {len(next_para)}"
    )

    # Verify prev_paragraph gets the LAST 2000 characters
    assert prev_para == long_paragraph[-2000:]

    # Verify next_paragraph gets the FIRST 2000 characters
    assert next_para == long_paragraph[:2000]


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text_includes_multiple_short_paragraphs(
    mock_new_paragraph, authenticated_client
):
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

    response = authenticated_client.post(
        "/generate-text",
        data={
            "user_text": "Current paragraph being edited",
            "title": "Test Document",
            "prev_paragraph": prev_context,
            "next_paragraph": next_context,
            "generation_mode": "rewrite",
        },
    )

    assert response.status_code == 200

    # Verify the callback was called
    mock_new_paragraph.assert_called_once()

    # Get the actual arguments passed to the callback
    call_args = mock_new_paragraph.call_args
    prev_para = call_args.kwargs["prev_paragraph"]
    next_para = call_args.kwargs["next_paragraph"]

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


def test_register_rejects_short_password(client):
    """Registration must enforce the 8-character minimum server-side."""
    response = client.post(
        "/auth/register",
        json={"email": "shortpass@example.com", "password": "abc12"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "REGISTER_INVALID_PASSWORD"
    assert "at least 8 characters" in detail["reason"]


def test_register_accepts_valid_password(client):
    """Registration with an 8+ character password must still work."""
    response = client.post(
        "/auth/register",
        json={"email": "longpass@example.com", "password": "goodpassword123"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "longpass@example.com"


def test_generate_text_rejects_an_unknown_mode(authenticated_client):
    """An unregistered mode used to fall back to another prompt silently."""
    response = authenticated_client.post(
        "/generate-text",
        data={"user_text": "Cats are nice.", "generation_mode": "summarize"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unknown generation mode 'summarize'" in detail
    for mode in ("ideas", "rewrite", "improve", "proofread"):
        assert mode in detail


def test_change_password_requires_authentication(client):
    response = client.post(
        "/user/change-password",
        json={"current_password": "testpassword123", "new_password": "another-one"},
    )
    assert response.status_code == 401


def test_change_password_rejects_wrong_current_password(authenticated_client):
    """A stolen token alone must not be enough to take over the account."""
    response = authenticated_client.post(
        "/user/change-password",
        json={"current_password": "not-my-password", "new_password": "a-new-password"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANGE_PASSWORD_INCORRECT_CURRENT"
    assert "current password" in detail["reason"].lower()
    # The old password still works.
    login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "testpassword123"},
        headers={"Authorization": ""},
    )
    assert login.status_code == 200


def test_change_password_enforces_minimum_length(authenticated_client):
    response = authenticated_client.post(
        "/user/change-password",
        json={"current_password": "testpassword123", "new_password": "short"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANGE_PASSWORD_INVALID_PASSWORD"
    assert "at least 8 characters" in detail["reason"]


def test_change_password_rejects_reusing_the_current_password(authenticated_client):
    response = authenticated_client.post(
        "/user/change-password",
        json={"current_password": "testpassword123", "new_password": "testpassword123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CHANGE_PASSWORD_INVALID_PASSWORD"


def test_change_password_succeeds_with_the_current_password(authenticated_client):
    response = authenticated_client.post(
        "/user/change-password",
        json={"current_password": "testpassword123", "new_password": "a-new-password"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Password changed"}

    old_login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "testpassword123"},
        headers={"Authorization": ""},
    )
    assert old_login.status_code == 400
    new_login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "a-new-password"},
        headers={"Authorization": ""},
    )
    assert new_login.status_code == 200


def test_index_offers_a_change_password_form(client):
    """The Settings dialog has an Account tab for changing the password."""
    html = client.get("/").text
    assert 'data-settings-tab="account"' in html
    assert 'id="account-settings"' in html
    for field in ("current-password", "new-password", "confirm-new-password"):
        assert f'id="{field}"' in html
        assert f'id="{field}" type="password"' in html or (
            f'type="password" id="{field}"' in html
        )
    assert 'id="change-password-btn"' in html


def test_change_email_requires_authentication(client):
    response = client.post(
        "/user/change-email",
        json={"current_password": "testpassword123", "new_email": "new@example.com"},
    )
    assert response.status_code == 401


def test_change_email_rejects_wrong_current_password(authenticated_client):
    """The email is the password-reset address: a token alone must not move it."""
    response = authenticated_client.post(
        "/user/change-email",
        json={"current_password": "not-my-password", "new_email": "new@example.com"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANGE_EMAIL_INCORRECT_CURRENT"
    assert "current password" in detail["reason"].lower()
    assert authenticated_client.get("/auth/check").json()["email"] == "test@example.com"


def test_change_email_rejects_the_current_address(authenticated_client):
    response = authenticated_client.post(
        "/user/change-email",
        json={"current_password": "testpassword123", "new_email": "test@example.com"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANGE_EMAIL_INVALID_EMAIL"
    assert "same" in detail["reason"].lower()


def test_change_email_rejects_an_address_in_use(authenticated_client):
    register = authenticated_client.post(
        "/auth/register",
        json={"email": "taken@example.com", "password": "someone-elses-pw"},
        headers={"Authorization": ""},
    )
    assert register.status_code == 201
    response = authenticated_client.post(
        "/user/change-email",
        json={"current_password": "testpassword123", "new_email": "taken@example.com"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANGE_EMAIL_ALREADY_EXISTS"
    assert "already" in detail["reason"].lower()
    assert authenticated_client.get("/auth/check").json()["email"] == "test@example.com"


def test_change_email_rejects_a_malformed_address(authenticated_client):
    response = authenticated_client.post(
        "/user/change-email",
        json={"current_password": "testpassword123", "new_email": "not-an-address"},
    )
    assert response.status_code == 422
    assert authenticated_client.get("/auth/check").json()["email"] == "test@example.com"


def test_change_email_succeeds_with_the_current_password(authenticated_client):
    response = authenticated_client.post(
        "/user/change-email",
        json={"current_password": "testpassword123", "new_email": "new@example.com"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Email changed",
        "email": "new@example.com",
    }

    # The session token identifies the user by id, so it keeps working and
    # now reports the new address.
    assert authenticated_client.get("/auth/check").json()["email"] == "new@example.com"

    old_login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "testpassword123"},
        headers={"Authorization": ""},
    )
    assert old_login.status_code == 400
    new_login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "new@example.com", "password": "testpassword123"},
        headers={"Authorization": ""},
    )
    assert new_login.status_code == 200


def test_users_me_routes_are_not_mounted(authenticated_client):
    """Self-service goes through /user/change-*, which verify the password.

    fastapi-users' ``/users/me`` routes are dropped; the superuser
    ``/users/{id}`` routes the admin guide relies on stay.
    """
    from writing_assistant.app.main import app

    paths = app.openapi()["paths"]
    assert "/users/me" not in paths
    assert set(paths["/users/{id}"]) == {"get", "patch", "delete"}

    # Without the /me route, a token alone can no longer set a password.
    response = authenticated_client.patch(
        "/users/me", json={"password": "taken-over-password"}
    )
    assert response.status_code != 200
    login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "testpassword123"},
        headers={"Authorization": ""},
    )
    assert login.status_code == 200


def test_index_offers_a_change_email_form(client):
    """The Account tab also changes the email address, on the same tab."""
    html = client.get("/").text
    assert html.count('data-settings-tab="account"') == 1
    account = html[html.index('id="account-settings"') :]
    account = account[: account.index("<!-- Load Document Modal -->")]
    assert 'id="change-email-form"' in account
    assert 'id="new-email"' in account
    assert 'type="email"' in account
    assert 'id="email-current-password"' in account
    assert 'id="change-email-btn"' in account
    assert 'id="change-password-form"' in account


def test_api_docs_report_the_installed_version():
    """``/docs`` and ``__version__`` come from the package metadata.

    The version used to be a hard-coded ``0.1.0`` that no release updated.
    """
    from importlib.metadata import version

    import writing_assistant
    from writing_assistant.app.main import app

    installed = version("talkpipe-writing-assistant")
    assert writing_assistant.__version__ == installed
    assert app.openapi()["info"]["version"] == installed


def test_save_as_dialog_asks_for_a_library_name(client):
    """The document goes to the server library, not to a ``.json`` file."""
    html = client.get("/").text
    dialog = html[html.index('id="save-as-modal"') :]
    dialog = dialog[: dialog.index("</form>") if "</form>" in dialog else 2000]
    assert 'for="save-as-filename">Name:' in dialog
    assert "library on the server" in dialog
    assert ".json extension" not in dialog


def test_ai_settings_say_where_the_key_is_kept(client):
    """Server URL, API key and environment variables are saved per account
    on the server (GET /user/preferences returns them), not only in the
    browser — the help text must not claim otherwise."""
    html = client.get("/").text
    assert "browser's local storage" not in html
    assert html.count("Saved with your account on the server") >= 1


def test_forgot_password_logs_the_token_instead_of_printing_it(
    authenticated_client, caplog
):
    """There is no mail delivery, so the reset token can only reach the server's
    log. Logging it (rather than printing it) lets a deployment route or
    silence it, and the message has to say that the log is now sensitive."""
    import logging

    with caplog.at_level(logging.WARNING, logger="writing_assistant.app.auth"):
        response = authenticated_client.post(
            "/auth/forgot-password",
            json={"email": "test@example.com"},
        )

    assert response.status_code == 202
    record = next(
        r for r in caplog.records if "Password reset requested" in r.getMessage()
    )
    message = record.getMessage()
    assert record.levelno == logging.WARNING
    assert "test@example.com" in message
    assert "No email is configured" in message
    assert "writing-assistant-admin reset-password" in message
