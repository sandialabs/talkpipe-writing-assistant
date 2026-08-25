"""End-to-end tests for the Textual TUI, driven with Textual's Pilot.

The app talks to the real FastAPI application in-process (ASGI transport),
so these cover the whole path from keystrokes to the database; only the LLM
call is mocked.
"""

from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from textual.widgets import Button, Input, Static, TextArea

from writing_assistant.app.database import get_async_session
from writing_assistant.app.main import app as fastapi_app
from writing_assistant.tui.app import (
    EditorScreen,
    LoginScreen,
    SettingsScreen,
    WritingAssistantApp,
    _suggest_filename,
    main,
    parse_env_vars_text,
)
from writing_assistant.tui.client import WritingAssistantClient
from writing_assistant.tui.session import Session

SIZE = (120, 45)
EMAIL = "pilot@example.com"
PASSWORD = "a-strong-password"


@pytest.fixture
async def tui_app(
    async_db_session: AsyncSession, tmp_path, monkeypatch
) -> AsyncGenerator[WritingAssistantApp, None]:
    """A TUI app wired to the in-process server with an isolated session file."""
    monkeypatch.setenv("WRITING_ASSISTANT_TUI_HOME", str(tmp_path))
    # The Settings dialog shows the Connection/Environment fields only when
    # the server allows custom env vars; pin the flag regardless of test order.
    monkeypatch.setattr("writing_assistant.app.main.ALLOW_CUSTOM_ENV_VARS", True)

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    fastapi_app.dependency_overrides[get_async_session] = override_get_async_session

    def factory(server_url: str, token: str | None) -> WritingAssistantClient:
        return WritingAssistantClient(
            server_url, token, transport=httpx.ASGITransport(app=fastapi_app)
        )

    yield WritingAssistantApp(
        Session(server_url="http://testserver"), client_factory=factory
    )
    fastapi_app.dependency_overrides.clear()


async def _register_and_login(pilot, app: WritingAssistantApp) -> EditorScreen:
    assert isinstance(app.screen, LoginScreen)
    await pilot.click("#toggle")  # switch to "create account"
    app.screen.query_one("#email", Input).value = EMAIL
    app.screen.query_one("#password", Input).value = PASSWORD
    app.screen.query_one("#confirm", Input).value = PASSWORD
    await pilot.click("#submit")
    await _settle(pilot)
    assert isinstance(app.screen, EditorScreen), _login_message(app)
    return app.screen


def _login_message(app: WritingAssistantApp) -> str:
    try:
        return str(app.screen.query_one("#login-message", Static).content)
    except Exception:
        return ""


async def _settle(pilot, rounds: int = 12) -> None:
    """Let workers and screen switches finish.

    Deliberately does not ``wait_for_complete`` on workers: an action worker
    that is waiting on a modal dialog would never finish until the test
    answers the dialog.
    """
    for _ in range(rounds):
        await pilot.pause(0.05)
    await pilot.pause()


def _text(widget: Static) -> str:
    return str(widget.content)


async def test_register_login_edit_generate_use_and_save(tui_app, mocker):
    generate = mocker.patch(
        "writing_assistant.app.main.cb.new_paragraph",
        return_value="A much better second paragraph.",
    )
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        assert _text(editor.query_one("#user", Static)) == EMAIL
        assert Session.load().token  # session persisted for next launch

        editor.title_input.value = "My Essay"
        area = editor.query_one("#editor", TextArea)
        area.load_text("First paragraph here.\n\nSecond paragraph here.\n\nThird one.")
        await pilot.pause()
        assert len(editor.sections) == 3
        assert editor.dirty

        # Put the cursor in the second section and ask for a rewrite.
        area.move_cursor((2, 3))
        await pilot.pause()
        assert editor.current_index == 1
        assert "Section 2 of 3" in _text(editor.query_one("#section-info", Static))
        await pilot.press("f6")
        await _settle(pilot)
        kwargs = generate.call_args.kwargs
        assert kwargs["generation_mode"] == "rewrite"
        assert kwargs["text"] == "Second paragraph here."
        assert kwargs["prev_paragraph"] == "First paragraph here."
        assert kwargs["next_paragraph"] == "Third one."
        assert kwargs["title"] == "My Essay"
        assert editor.sections[1].generated_text == "A much better second paragraph."
        assert "much better" in _text(editor.query_one("#suggestion-text", Static))
        assert not editor.query_one("#use-suggestion", Button).disabled

        # Apply the suggestion to the section.
        await pilot.press("ctrl+u")
        await pilot.pause()
        assert area.text == (
            "First paragraph here.\n\nA much better second paragraph.\n\nThird one."
        )
        assert editor.sections[1].generated_text == "A much better second paragraph."

        # Save As → prompt for a filename.
        await pilot.press("ctrl+s")
        await _settle(pilot)
        prompt = app.screen
        assert prompt is not editor
        prompt.query_one("#value", Input).value = "essay"
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename == "essay.json"
        assert not editor.dirty
        assert "essay.json" in _text(editor.query_one("#filename", Static))

        # The document is in the server's library with its suggestion.
        saved = await editor.client.load_document("essay.json")
        assert saved["title"] == "My Essay"
        assert (
            saved["sections"][1]["generated_text"] == "A much better second paragraph."
        )
        assert saved["metadata"]["writing_style"] == "formal"

        # Plain save now updates in place.
        area.insert(" More.")
        await pilot.pause()
        assert editor.dirty
        await pilot.press("ctrl+s")
        await _settle(pilot)
        assert not editor.dirty
        assert "More." in (await editor.client.load_document("essay.json"))["content"]
        assert Session.load().last_filename == "essay.json"


async def test_open_document_picker_and_reopen_on_restart(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await editor.client.save_document(
            "one.json", {"title": "One", "content": "alpha\n\nbeta", "sections": []}
        )
        await editor.client.save_document(
            "two.json", {"title": "Two", "content": "gamma", "sections": []}
        )
        await pilot.press("ctrl+o")
        await _settle(pilot)
        picker = app.screen
        assert picker is not editor
        options = picker.query_one("#entries")
        # Newest first: two.json then one.json; pick the second entry.
        options.highlighted = 1
        await pilot.click("#open")
        await _settle(pilot)
        assert editor.filename == "one.json"
        assert editor.title_input.value == "One"
        assert editor.query_one("#editor", TextArea).text == "alpha\n\nbeta"
        assert len(editor.sections) == 2

    # A second launch with the saved token skips login and reopens one.json.
    app2 = WritingAssistantApp(Session.load(), client_factory=app._client_factory)
    async with app2.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert isinstance(app2.screen, EditorScreen)
        assert app2.screen.filename == "one.json"
        assert app2.screen.title_input.value == "One"


async def test_snapshot_create_and_revert(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        area.load_text("version one")
        editor.title_input.value = "Snap"
        editor._save_as("snap.json", save_as=True)
        await _settle(pilot)
        assert editor.filename == "snap.json"

        editor.action_snapshot()
        await _settle(pilot)
        assert len(await editor.client.list_snapshots("snap.json")) == 1

        area.load_text("version two")
        await pilot.pause()
        editor._save_as("snap.json", save_as=False)
        await _settle(pilot)

        editor.action_revert()
        await _settle(pilot)
        picker = app.screen
        assert picker is not editor
        picker.query_one("#entries").highlighted = 0
        await pilot.click("#open")
        await _settle(pilot)
        assert area.text == "version one"
        assert editor.dirty


async def test_new_document_import_export_and_delete(tui_app, tmp_path):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.action_new()
        await _settle(pilot)
        dialog = app.screen
        dialog.query_one("#title", Input).value = "Fresh"
        dialog.query_one("#outline", TextArea).load_text("para one\n\npara two")
        await pilot.click("#create")
        await _settle(pilot)
        assert editor.title_input.value == "Fresh"
        assert len(editor.sections) == 2
        assert editor.filename is None

        export_path = tmp_path / "out" / "fresh.json"
        editor.action_export()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = str(export_path)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert export_path.exists()

        # Import it back into a blank editor (discarding unsaved changes).
        editor.query_one("#editor", TextArea).load_text("")
        editor.title_input.value = ""
        editor._mark_dirty(False)
        editor.action_import()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = str(export_path)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.title_input.value == "Fresh"
        assert editor.query_one("#editor", TextArea).text == "para one\n\npara two"

        # Save, then delete via the File menu action (with confirmation).
        editor._save_as("fresh.json", save_as=True)
        await _settle(pilot)
        editor.action_delete()
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename is None
        assert await editor.client.list_documents() == []


async def test_settings_dialog_saves_document_metadata_and_defaults(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings, SettingsScreen)
        settings.query_one("#target_audience", Input).value = "engineers"
        settings.query_one("#word_limit", Input).value = "120"
        settings.query_one("#tabs").active = "tab-ai"
        settings.query_one("#model", Input).value = "llama3.1:8b"
        settings.query_one("#source").value = "ollama"
        settings.query_one("#environment_variables", TextArea).load_text(
            "FOO=bar\n# comment\n"
        )
        settings.query_one("#default", Button).press()
        await _settle(pilot)
        assert editor.metadata["target_audience"] == "engineers"
        assert editor.metadata["word_limit"] == 120
        assert editor.metadata["source"] == "ollama"
        assert editor.ai["environment_variables"] == {"FOO": "bar"}
        prefs = await editor.client.get_preferences()
        assert prefs["target_audience"] == "engineers"
        assert prefs["model"] == "llama3.1:8b"
        assert prefs["environment_variables"] == {"FOO": "bar"}

        fields = editor._generation_fields("ideas", 0) if editor.sections else None
        assert fields is None  # no sections yet
        editor.query_one("#editor", TextArea).load_text("some text")
        await pilot.pause()
        fields = editor._generation_fields("ideas", 0)
        assert fields["source"] == "ollama"
        assert fields["model"] == "llama3.1:8b"
        assert fields["word_limit"] == 120
        assert fields["environment_variables"] == '{"FOO": "bar"}'


async def test_settings_test_connection_reports_result(tui_app, mocker):
    mocker.patch(
        "writing_assistant.app.main.ai_connection.test_connection",
        return_value={
            "available": False,
            "source": "ollama",
            "model": "m",
            "reason": "Could not connect to the Ollama server.",
        },
    )
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        settings.query_one("#tabs").active = "tab-ai"
        settings.query_one("#test", Button).press()
        await _settle(pilot)
        status = _text(settings.query_one("#connection-status", Static))
        assert "Could not connect to the Ollama server" in status


async def test_generation_error_is_shown_not_fatal(tui_app, mocker):
    mocker.patch(
        "writing_assistant.app.main.cb.new_paragraph",
        side_effect=ValueError("Model name and source must be provided"),
    )
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("draft text")
        await pilot.pause()
        await pilot.press("f5")
        await _settle(pilot)
        shown = _text(editor.query_one("#suggestion-text", Static))
        assert shown.startswith("Error:")
        assert "Settings" in shown
        assert isinstance(app.screen, EditorScreen)


async def test_login_rejects_bad_password_and_stays(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        assert isinstance(app.screen, LoginScreen)
        app.screen.query_one("#email", Input).value = "nobody@example.com"
        app.screen.query_one("#password", Input).value = "nope"
        await pilot.click("#submit")
        await _settle(pilot)
        assert isinstance(app.screen, LoginScreen)
        assert "Incorrect email or password" in _login_message(app)


async def test_stale_token_returns_to_login(tui_app):
    app = tui_app
    app.session.token = "stale"
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert isinstance(app.screen, LoginScreen)
        assert "expired" in _login_message(app)


async def test_logout_returns_to_login_and_forgets_token(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.action_logout()
        await _settle(pilot)
        assert isinstance(app.screen, LoginScreen)
        assert Session.load().token is None


def test_parse_env_vars_text():
    assert parse_env_vars_text("A=1\n\n# c\nB = two=2\n") == {"A": "1", "B": "two=2"}
    with pytest.raises(ValueError, match="KEY=VALUE"):
        parse_env_vars_text("novalue")
    with pytest.raises(ValueError, match="variable name"):
        parse_env_vars_text("=x")


def test_suggest_filename():
    assert _suggest_filename("My Great Essay!") == "my-great-essay.json"
    assert _suggest_filename("") == "document.json"


def test_main_parses_server_and_logout(monkeypatch, tmp_path):
    monkeypatch.setenv("WRITING_ASSISTANT_TUI_HOME", str(tmp_path))
    Session(server_url="http://old:1", token="tok").save()
    captured: dict = {}

    class FakeApp:
        def __init__(self, session):
            captured["session"] = session

        def run(self):
            captured["ran"] = True

    monkeypatch.setattr("writing_assistant.tui.app.WritingAssistantApp", FakeApp)
    main(["--server", "http://new:2/"])
    assert captured["ran"]
    assert captured["session"].server_url == "http://new:2"
    assert captured["session"].token is None  # different server forgets token

    Session(server_url="http://old:1", token="tok").save()
    main(["--logout"])
    assert captured["session"].token is None
    assert Session.load().token is None
