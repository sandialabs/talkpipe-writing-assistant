"""Quick-access writing templates: the per-user template endpoints."""

import uuid

from fastapi_users.password import PasswordHelper

from writing_assistant.app.models import User

EMAIL_SETTINGS = {
    "writing_style": "casual",
    "target_audience": "a colleague",
    "tone": "friendly",
    "background_context": "Replying to internal email threads.",
    "generation_directive": "Keep it to three short paragraphs.",
    "word_limit": 120,
}


def _save(client, name, settings=EMAIL_SETTINGS):
    return client.post("/templates/save", json={"name": name, "settings": settings})


def test_templates_require_authentication(client):
    assert client.get("/templates/list").status_code == 401
    assert _save(client, "Email").status_code == 401
    assert client.delete("/templates/delete/1").status_code == 401


def test_template_list_is_empty_at_first(authenticated_client):
    response = authenticated_client.get("/templates/list")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "templates": []}


def test_save_lists_and_deletes_a_template(authenticated_client):
    response = _save(authenticated_client, "Email")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message"] == "Template created"
    template = body["template"]
    assert template["name"] == "Email"
    assert template["settings"] == EMAIL_SETTINGS
    assert isinstance(template["id"], int)

    listed = authenticated_client.get("/templates/list").json()["templates"]
    assert [t["name"] for t in listed] == ["Email"]
    assert listed[0]["settings"] == EMAIL_SETTINGS
    assert listed[0]["id"] == template["id"]
    assert listed[0]["modified"].endswith("+00:00")

    response = authenticated_client.delete(f"/templates/delete/{template['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert authenticated_client.get("/templates/list").json()["templates"] == []


def test_saving_the_same_name_updates_in_place(authenticated_client):
    first = _save(authenticated_client, "Email").json()["template"]
    changed = {**EMAIL_SETTINGS, "tone": "professional", "word_limit": None}
    response = _save(authenticated_client, "  Email ", changed)
    assert response.json()["message"] == "Template updated"
    assert response.json()["template"]["id"] == first["id"]
    listed = authenticated_client.get("/templates/list").json()["templates"]
    assert len(listed) == 1
    assert listed[0]["settings"]["tone"] == "professional"
    assert listed[0]["settings"]["word_limit"] is None


def test_templates_are_listed_by_name(authenticated_client):
    for name in ("Weekly report", "Email", "Cover letter"):
        _save(authenticated_client, name)
    listed = authenticated_client.get("/templates/list").json()["templates"]
    assert [t["name"] for t in listed] == ["Cover letter", "Email", "Weekly report"]


def test_template_settings_are_normalised(authenticated_client):
    # The web form sends an empty word limit as null and may send extra keys
    # (source, model) that are not part of a writing template.
    response = _save(
        authenticated_client,
        "Sparse",
        {"writing_style": "academic", "word_limit": "", "source": "ollama"},
    )
    assert response.status_code == 200, response.text
    settings = response.json()["template"]["settings"]
    assert settings == {
        "writing_style": "academic",
        "target_audience": "",
        "tone": "neutral",
        "background_context": "",
        "generation_directive": "",
        "word_limit": None,
    }
    assert (
        _save(authenticated_client, "Str", {"word_limit": "250"}).json()["template"][
            "settings"
        ]["word_limit"]
        == 250
    )


def test_template_save_rejects_bad_input(authenticated_client):
    assert _save(authenticated_client, "   ").status_code == 422
    assert _save(authenticated_client, "x" * 101).status_code == 422
    assert _save(authenticated_client, "Email", {"word_limit": "lots"}).status_code == (
        422
    )
    response = authenticated_client.post("/templates/save", json={"name": "Email"})
    assert response.status_code == 422


def test_deleting_a_missing_template_reports_an_error(authenticated_client):
    response = authenticated_client.delete("/templates/delete/999")
    assert response.status_code == 200
    assert response.json() == {"status": "error", "message": "Template not found"}


async def test_templates_are_private_to_their_owner(
    authenticated_client, async_db_session
):
    template = _save(authenticated_client, "Email").json()["template"]

    other = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=PasswordHelper().hash("otherpassword123"),
        is_active=True,
        is_verified=True,
    )
    async_db_session.add(other)
    await async_db_session.commit()
    login = authenticated_client.post(
        "/auth/jwt/login",
        data={"username": "other@example.com", "password": "otherpassword123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = authenticated_client.get("/templates/list", headers=headers).json()
    assert listed["templates"] == []
    response = authenticated_client.delete(
        f"/templates/delete/{template['id']}", headers=headers
    )
    assert response.json()["status"] == "error"
    # Still there for its owner; a same-named template for the other user is
    # a separate row.
    assert len(authenticated_client.get("/templates/list").json()["templates"]) == 1
    created = authenticated_client.post(
        "/templates/save",
        json={"name": "Email", "settings": {}},
        headers=headers,
    ).json()
    assert created["message"] == "Template created"
    assert created["template"]["id"] != template["id"]


def test_index_page_offers_templates(client):
    """The web UI has the Templates menu, the Settings controls, and the
    Save/Discard/Cancel prompt the template flow relies on."""
    html = client.get("/").text
    assert 'id="templates-menu-btn"' in html
    assert 'id="manage-templates-btn"' in html
    assert 'id="template-name"' in html
    assert 'id="save-template-btn"' in html
    assert 'id="templates-list"' in html
    assert 'id="unsaved-document-modal"' in html
