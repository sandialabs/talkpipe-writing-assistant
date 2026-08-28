"""The TUI's REST client, exercised against the real FastAPI app in-process."""

import json
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from writing_assistant.app.database import get_async_session
from writing_assistant.app.main import app
from writing_assistant.tui.client import (
    ApiError,
    AuthError,
    WritingAssistantClient,
    _detail_message,
)


@pytest.fixture
async def tui_client(
    async_db_session: AsyncSession,
) -> AsyncGenerator[WritingAssistantClient, None]:
    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session
    client = WritingAssistantClient(
        "http://testserver", transport=httpx.ASGITransport(app=app)
    )
    yield client
    await client.aclose()
    app.dependency_overrides.clear()


async def test_register_login_and_check(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    token = await tui_client.login("tui@example.com", "a-strong-password")
    assert token
    assert tui_client.token == token
    info = await tui_client.check_auth()
    assert info["email"] == "tui@example.com"
    config = await tui_client.server_config()
    assert "allow_custom_env_vars" in config


async def test_login_bad_credentials_is_readable(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    with pytest.raises(ApiError) as excinfo:
        await tui_client.login("tui@example.com", "wrong")
    assert excinfo.value.message == "Incorrect email or password."


async def test_register_duplicate_is_readable(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    with pytest.raises(ApiError) as excinfo:
        await tui_client.register("tui@example.com", "a-strong-password")
    assert "already exists" in excinfo.value.message


async def test_unauthenticated_request_raises_auth_error(
    tui_client: WritingAssistantClient,
):
    with pytest.raises(AuthError):
        await tui_client.list_documents()
    tui_client.token = "not-a-real-token"
    with pytest.raises(AuthError):
        await tui_client.check_auth()


async def test_document_round_trip(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    await tui_client.login("tui@example.com", "a-strong-password")

    assert await tui_client.list_documents() == []
    document = {"title": "T", "content": "hello\n\nworld", "sections": []}
    message = await tui_client.save_document("doc.json", document)
    assert message == "Document created"
    listing = await tui_client.list_documents()
    assert [d["filename"] for d in listing] == ["doc.json"]
    assert listing[0]["title"] == "T"

    loaded = await tui_client.load_document("doc.json")
    assert loaded == document

    document["content"] = "changed"
    assert await tui_client.save_document("doc.json", document) == "Document updated"
    assert (await tui_client.load_document("doc.json"))["content"] == "changed"

    copy = await tui_client.save_document("copy.json", document, save_as=True)
    assert copy == "Document created"
    raw = await tui_client.download_document("copy.json")
    assert json.loads(raw) == document

    with pytest.raises(ApiError, match="not found"):
        await tui_client.load_document("missing.json")

    assert "deleted" in (await tui_client.delete_document("copy.json"))
    assert [d["filename"] for d in await tui_client.list_documents()] == ["doc.json"]


async def test_snapshot_round_trip(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    await tui_client.login("tui@example.com", "a-strong-password")
    document = {"title": "T", "content": "v1"}
    await tui_client.save_document("doc.json", document)

    assert await tui_client.list_snapshots("doc.json") == []
    message = await tui_client.create_snapshot("doc.json")
    assert message.startswith("Snapshot created")
    snapshots = await tui_client.list_snapshots("doc.json")
    assert len(snapshots) == 1
    name = snapshots[0]["filename"]

    document["content"] = "v2"
    await tui_client.save_document("doc.json", document)
    assert (await tui_client.load_snapshot(name))["content"] == "v1"

    with pytest.raises(ApiError, match="not found"):
        await tui_client.list_snapshots("missing.json")


async def test_preferences_round_trip(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    await tui_client.login("tui@example.com", "a-strong-password")
    assert await tui_client.get_preferences() == {}
    prefs = {"source": "ollama", "model": "llama3.1:8b", "writing_style": "casual"}
    await tui_client.save_preferences(prefs)
    assert await tui_client.get_preferences() == prefs


async def test_generate_text_and_test_connection(
    tui_client: WritingAssistantClient, mocker
):
    await tui_client.register("tui@example.com", "a-strong-password")
    await tui_client.login("tui@example.com", "a-strong-password")

    new_paragraph = mocker.patch(
        "writing_assistant.app.main.cb.new_paragraph", return_value="generated"
    )
    text = await tui_client.generate_text(
        {
            "user_text": "draft",
            "generation_mode": "improve",
            "word_limit": None,
            "source": "ollama",
            "model": "m",
        }
    )
    assert text == "generated"
    kwargs = new_paragraph.call_args.kwargs
    assert kwargs["generation_mode"] == "improve"
    assert kwargs["metadata"].source == "ollama"

    new_paragraph.side_effect = ValueError("Model name and source must be provided")
    with pytest.raises(ApiError) as excinfo:
        await tui_client.generate_text(
            {"user_text": "draft", "generation_mode": "ideas"}
        )
    assert "Settings" in excinfo.value.message

    probe = mocker.patch(
        "writing_assistant.app.main.ai_connection.test_connection",
        return_value={"available": True, "source": "ollama", "model": "m"},
    )
    report = await tui_client.test_connection({"source": "ollama", "model": "m"})
    assert report["available"] is True
    assert probe.call_args.args[:2] == ("ollama", "m")


async def test_logout_clears_token(tui_client: WritingAssistantClient):
    await tui_client.register("tui@example.com", "a-strong-password")
    await tui_client.login("tui@example.com", "a-strong-password")
    await tui_client.logout()
    assert tui_client.token is None
    await tui_client.logout()  # idempotent


async def test_connection_refused_is_readable():
    client = WritingAssistantClient("http://127.0.0.1:1", timeout=2)
    try:
        with pytest.raises(ApiError) as excinfo:
            await client.server_config()
    finally:
        await client.aclose()
    assert "Could not connect" in excinfo.value.message
    assert "writing-assistant" in excinfo.value.message


def test_detail_message_shapes():
    def response(body, status=400):
        return httpx.Response(status, json=body)

    assert _detail_message(response({"detail": "LOGIN_BAD_CREDENTIALS"})) == (
        "Incorrect email or password."
    )
    assert (
        _detail_message(
            response(
                {"detail": {"code": "REGISTER_INVALID_PASSWORD", "reason": "too short"}}
            )
        )
        == "too short"
    )
    assert (
        _detail_message(
            response({"detail": [{"loc": ["body", "email"], "msg": "invalid"}]})
        )
        == "email: invalid"
    )
    assert (
        _detail_message(response({"detail": [{"loc": ["query", "q"], "msg": "bad"}]}))
        == "query.q: bad"
    )
    assert _detail_message(response({"message": "boom"})) == "boom"
    # A short plain-text body is kept but tagged with its status.
    assert _detail_message(httpx.Response(500, text="oops")) == "HTTP 500: oops"
    assert _detail_message(httpx.Response(502, text="")) == "HTTP 502"


def test_detail_message_does_not_dump_html_error_pages():
    """A wrong Server URL often points at some other HTTP service whose error
    page is a whole HTML document; the message must summarise, not dump it."""
    page = "<!doctype html><html><head><title>Example</title></head>" + "x" * 500
    by_body = _detail_message(httpx.Response(404, text="<html>nope</html>"))
    assert "<html>" not in by_body
    assert "writing-assistant server" in by_body
    by_type = _detail_message(
        httpx.Response(200, text=page, headers={"content-type": "text/html"})
    )
    assert "<!doctype" not in by_type.lower()
    assert "HTML page" in by_type
    # An over-long non-HTML body is capped rather than flooding the UI.
    capped = _detail_message(httpx.Response(500, text="z" * 5000))
    assert len(capped) < 260
    assert capped.endswith("…")


async def test_test_connection_explains_server_without_endpoint():
    """An older server has no /ai/test-connection; say so instead of 'Not Found'."""

    async def old_server(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Not Found"})

    client = WritingAssistantClient(
        "http://old-server:8001", token="t", transport=httpx.MockTransport(old_server)
    )
    try:
        with pytest.raises(ApiError) as excinfo:
            await client.test_connection({"source": "ollama", "model": "m"})
    finally:
        await client.aclose()
    message = excinfo.value.message
    assert message != "Not Found"
    assert "http://old-server:8001" in message
    assert "1.0.0b1" in message
    assert "upgrade" in message.lower()
