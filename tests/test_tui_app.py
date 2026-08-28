"""End-to-end tests for the Textual TUI, driven with Textual's Pilot.

The app talks to the real FastAPI application in-process (ASGI transport),
so these cover the whole path from keystrokes to the database; only the LLM
call is mocked.
"""

import asyncio
import time
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from textual.command import CommandList
from textual.widgets import Button, Input, Static, TextArea
from textual.widgets._tabbed_content import ContentTabs

from writing_assistant.app.database import get_async_session
from writing_assistant.app.main import app as fastapi_app
from writing_assistant.tui.app import (
    HELP_TEXT,
    ConfirmScreen,
    EditorScreen,
    LoginScreen,
    NewDocumentScreen,
    PickerScreen,
    PromptScreen,
    SettingsScreen,
    UnsavedChangesScreen,
    WritingAssistantApp,
    _format_timestamp,
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


async def test_opening_a_document_does_not_mark_it_dirty(tui_app):
    """TextArea.Changed arrives after the load; it must not count as an edit."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await editor.client.save_document(
            "clean.json", {"title": "Clean", "content": "alpha\n\nbeta", "sections": []}
        )
        await editor._open_document("clean.json")
        await _settle(pilot)
        assert editor.filename == "clean.json"
        assert not editor.dirty
        assert "●" not in _text(editor.query_one("#filename", Static))

        # Quit must not ask about unsaved changes when nothing changed.
        await pilot.press("ctrl+q")
        await _settle(pilot)
        assert not app.is_running

    app2 = WritingAssistantApp(Session.load(), client_factory=app._client_factory)
    async with app2.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert isinstance(app2.screen, EditorScreen)
        assert app2.screen.filename == "clean.json"
        assert not app2.screen.dirty
        # A real edit still marks the document dirty.
        app2.screen.query_one("#editor", TextArea).insert("x")
        await pilot.pause()
        assert app2.screen.dirty


async def test_save_ai_settings_applies_model_to_open_document(tui_app):
    """Like the web client, saving AI settings updates the document's source/model."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.metadata["source"] = "ollama"
        editor.metadata["model"] = "old-model"
        editor.query_one("#editor", TextArea).load_text("some text")
        await pilot.pause()
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        settings.query_one("#tabs").active = "tab-ai"
        settings.query_one("#source").value = "ollama"
        settings.query_one("#model", Input).value = "new-model"
        settings.query_one("#ai", Button).press()
        await _settle(pilot)
        assert editor.metadata["model"] == "new-model"
        assert editor._generation_fields("ideas", 0)["model"] == "new-model"


async def test_connection_status_is_visible_without_scrolling(tui_app, mocker):
    mocker.patch(
        "writing_assistant.app.main.ai_connection.test_connection",
        return_value={"available": True, "source": "ollama", "model": "m"},
    )
    app = tui_app
    # 40 rows: the AI form is taller than the dialog, so a status line at the
    # bottom of the scrolling form would be out of sight.
    async with app.run_test(size=(120, 40)) as pilot:
        await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        settings.query_one("#tabs").active = "tab-ai"
        await _settle(pilot)
        settings.query_one("#test", Button).press()
        await _settle(pilot)
        status = settings.query_one("#connection-status", Static)
        assert "Connected to ollama / m" in _text(status)
        region = status.region
        assert region.height >= 1
        assert 0 <= region.y < app.size.height
        # Not inside the scrolling form: the buttons follow it on screen.
        assert region.y < settings.query_one("#ai", Button).region.y


async def test_login_buttons_fit_in_24_rows(tui_app):
    app = tui_app
    async with app.run_test(size=(80, 24)) as pilot:
        await _settle(pilot)
        assert isinstance(app.screen, LoginScreen)
        for button_id in ("#submit", "#toggle", "#quit"):
            region = app.screen.query_one(button_id, Button).region
            assert region.height == 3, button_id
            assert region.y + region.height <= 24, button_id
        # Register mode adds a field; the box scrolls rather than clipping.
        await pilot.click("#toggle")
        await _settle(pilot)
        app.screen.query_one("#submit", Button).focus()
        await _settle(pilot)
        region = app.screen.query_one("#submit", Button).region
        assert region.y >= 0
        assert region.y + region.height <= 24


async def test_help_dialog_fits_small_terminal(tui_app):
    app = tui_app
    async with app.run_test(size=(80, 24)) as pilot:
        # Register with the keyboard: in register mode the login box scrolls.
        await pilot.click("#toggle")
        app.screen.query_one("#email", Input).value = EMAIL
        app.screen.query_one("#password", Input).value = PASSWORD
        confirm = app.screen.query_one("#confirm", Input)
        confirm.value = PASSWORD
        confirm.focus()
        await pilot.press("enter")
        await _settle(pilot)
        editor = app.screen
        assert isinstance(editor, EditorScreen), _login_message(app)
        await pilot.press("f1")
        await _settle(pilot)
        dialog = app.screen
        assert dialog is not editor
        ok = dialog.query_one("#ok", Button)
        assert ok.region.y + ok.region.height <= 24
        assert ok.region.x + ok.region.width <= 80
        body = dialog.query_one(".dialog-body")
        assert body.region.x + body.region.width <= 80
        await pilot.press("escape")
        await _settle(pilot)
        assert app.screen is editor


async def test_tab_moves_focus_out_of_the_editor(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        area.load_text("one\n\ntwo")
        await pilot.pause()
        area.focus()
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is not area
        assert area.text == "one\n\ntwo"


async def test_login_footer_shows_quit(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert isinstance(app.screen, LoginScreen)
        keys = {binding.key for _, binding, *_ in app.screen.active_bindings.values()}
        assert "ctrl+q" in keys
        shown = [
            binding
            for _, binding, *_ in app.screen.active_bindings.values()
            if binding.key == "ctrl+q"
        ]
        assert any(b.show for b in shown)


async def test_first_run_hint_when_no_ai_configured(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        assert not editor.ai["source"]
        assert not editor.metadata.get("source")
        notifications = [n.message for n in app._notifications]
        assert any("F3" in message for message in notifications), notifications


async def test_save_as_asks_before_overwriting_another_document(tui_app):
    """Save As onto a name already in the library must not silently replace it."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await editor.client.save_document(
            "essay.json", {"title": "Keep me", "content": "original", "sections": []}
        )
        area = editor.query_one("#editor", TextArea)
        area.load_text("something else")
        await pilot.pause()

        editor.action_save_as()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = "essay.json"
        await pilot.click("#confirm")
        await _settle(pilot)
        confirm = app.screen
        assert isinstance(confirm, ConfirmScreen), type(confirm).__name__
        assert "essay.json" in " ".join(_text(w) for w in confirm.query(Static))
        await pilot.click("#cancel")
        await _settle(pilot)
        assert editor.filename is None
        assert (await editor.client.load_document("essay.json"))["content"] == (
            "original"
        )

        # Confirming does overwrite.
        editor.action_save_as()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = "essay.json"
        await pilot.click("#confirm")
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename == "essay.json"
        assert (await editor.client.load_document("essay.json"))["content"] == (
            "something else"
        )

        # Saving the open document under its own name never asks.
        area.insert(" more")
        await pilot.pause()
        editor.action_save_as()
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)
        assert not editor.dirty


def test_format_timestamp_renders_server_utc_in_local_time(monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("needs POSIX time zones")
    monkeypatch.setenv("TZ", "America/Denver")
    time.tzset()
    try:
        # The server stamps in UTC without an offset; the snapshot created at
        # 07:48 Mountain time must not be listed as 13:48.
        assert _format_timestamp("2026-08-25T13:48:12.509942") == "2026-08-25 07:48"
        assert _format_timestamp("2026-08-25T13:48:12+00:00") == "2026-08-25 07:48"
        assert _format_timestamp("") == ""
        assert _format_timestamp("yesterday") == "yesterday"
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()


async def test_command_palette_finds_editor_commands(tui_app):
    """Ctrl+P (advertised in the footer) lists the app's own actions."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await pilot.press("ctrl+p")
        await _settle(pilot)
        await pilot.press(*"snapshot")
        await _settle(pilot, rounds=20)
        options = app.screen.query_one(CommandList)
        prompts = [
            str(options.get_option_at_index(i).prompt)
            for i in range(options.option_count)
        ]
        assert any("Create snapshot" in p for p in prompts), prompts
        await pilot.press("enter")
        await _settle(pilot)
        # The command ran: an unsaved document has no snapshots to create.
        assert isinstance(app.screen, EditorScreen)
        assert editor.filename is None
        assert any(
            "before creating a snapshot" in str(n.message) for n in app._notifications
        ), [n.message for n in app._notifications]


async def test_settings_tab_order_has_no_invisible_stop(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings.focused, ContentTabs)
        await pilot.press("tab")
        await pilot.pause()
        assert settings.focused is not None
        assert settings.focused.id == "writing_style", settings.focused


async def test_save_ai_settings_on_empty_document_is_not_an_unsaved_change(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        settings.query_one("#tabs").active = "tab-ai"
        settings.query_one("#source").value = "ollama"
        settings.query_one("#model", Input).value = "llama3.2"
        settings.query_one("#ai", Button).press()
        await _settle(pilot)
        assert editor.metadata["model"] == "llama3.2"
        assert not editor.dirty
        # Quitting must not ask about changes that were never made.
        await pilot.press("ctrl+q")
        await _settle(pilot)
        assert not app.is_running


async def test_suggestion_panel_shows_several_lines_at_common_sizes(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
    for size, text_rows in (((80, 24), 4), ((100, 30), 5)):
        # The saved token skips login, so each size starts in the editor.
        app = WritingAssistantApp(
            Session.load(), client_factory=tui_app._client_factory
        )
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, EditorScreen)
            scroll = editor.query_one("#suggestion-scroll")
            assert scroll.region.height >= text_rows, (size, scroll.region.height)
            assert editor.query_one("#editor", TextArea).region.height >= 6
            # ...and nothing is pushed off the bottom of the terminal.
            bar = editor.query_one("#mode-bar").region
            assert bar.bottom <= size[1] - 1, (size, bar)


async def test_new_document_dialog_fits_small_terminal(tui_app):
    """At 80x24 the Create/Cancel buttons were below the bottom of the screen."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
    app = WritingAssistantApp(Session.load(), client_factory=tui_app._client_factory)
    async with app.run_test(size=(80, 24)) as pilot:
        await _settle(pilot)
        await pilot.press("ctrl+n")
        await _settle(pilot)
        dialog = app.screen
        assert dialog.query("#create")
        create = dialog.query_one("#create", Button).region
        assert create.y >= 0, create
        assert create.bottom <= 24, create
        assert dialog.query_one("#outline", TextArea).region.height >= 3
        # ...and it is still usable: type a title and click Create.
        dialog.query_one("#title", Input).value = "Fits"
        await pilot.click("#create")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)
        assert app.screen.title_input.value == "Fits"


async def test_short_terminal_keeps_suggestion_panel_on_screen(tui_app):
    """At 20 rows the panel and mode buttons were laid out below the screen."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
    for size in ((70, 20), (80, 20), (60, 16)):
        app = WritingAssistantApp(
            Session.load(), client_factory=tui_app._client_factory
        )
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, EditorScreen)
            assert editor.has_class("compact"), size
            panel = editor.query_one("#suggestion-panel").region
            assert panel.bottom <= size[1] - 1, (size, panel)
            assert editor.query_one("#suggestion-scroll").region.height >= 3
            assert editor.query_one("#editor", TextArea).region.height >= 4
            # The mode bar is hidden; the keys still generate.
            assert not editor.query_one("#mode-bar").display
            # Narrow (below 90 columns): shorter labels so the row fits.
            assert editor.has_class("narrow"), size
            assert str(editor.query_one("#mode-ideas", Button).label) == "Ideas"
    # Back at 80x24 the mode bar is back (with short labels: the full ones
    # need 90 columns, see test_mode_bar_fits_from_ninety_columns).
    app = WritingAssistantApp(Session.load(), client_factory=tui_app._client_factory)
    async with app.run_test(size=(80, 24)) as pilot:
        await _settle(pilot)
        editor = app.screen
        assert not editor.has_class("compact")
        assert editor.has_class("narrow")
        assert str(editor.query_one("#mode-ideas", Button).label) == "Ideas"
        bar = editor.query_one("#mode-bar").region
        assert bar.height == 3, bar
        assert bar.bottom <= 23, bar
        assert editor.query_one("#editor", TextArea).region.height >= 9


async def test_mode_bar_fits_from_ninety_columns(tui_app):
    """At 80 columns the full labels were clipped ("Use This Text" lost its key)."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
    for width, narrow in ((89, True), (90, False), (100, False)):
        app = WritingAssistantApp(
            Session.load(), client_factory=tui_app._client_factory
        )
        async with app.run_test(size=(width, 30)) as pilot:
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, EditorScreen)
            assert editor.has_class("narrow") is narrow, width
            expected = "Use (Ctrl+U)" if narrow else "Use This Text (Ctrl+U)"
            use = editor.query_one("#use-suggestion", Button)
            assert str(use.label) == expected
            bar = editor.query_one("#mode-bar").region
            for button in editor.query("#mode-bar Button").results(Button):
                region = button.region
                assert region.width >= len(str(button.label)) + 2, (width, button)
                assert region.right <= bar.right, (width, button.label, region, bar)


async def test_too_small_terminal_is_announced(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
    app = WritingAssistantApp(Session.load(), client_factory=tui_app._client_factory)
    async with app.run_test(size=(50, 14)) as pilot:
        await _settle(pilot)
        messages = [str(n.message) for n in app._notifications]
        assert any("50x14" in m and "60x16" in m for m in messages), messages


async def test_settings_f3_switches_tabs_and_fits_narrow_terminal(tui_app):
    """Keyboard users had no documented way to reach the AI Settings tab."""
    app = tui_app
    async with app.run_test(size=(70, 24)) as pilot:
        # Register from the keyboard (the login box scrolls at this size).
        await pilot.click("#toggle")
        app.screen.query_one("#email", Input).value = EMAIL
        app.screen.query_one("#password", Input).value = PASSWORD
        confirm = app.screen.query_one("#confirm", Input)
        confirm.value = PASSWORD
        confirm.focus()
        await pilot.press("enter")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen), _login_message(app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings, SettingsScreen)
        tabs = settings.query_one("#tabs")
        assert tabs.active == "tab-document"
        await pilot.press("f3")
        await _settle(pilot)
        assert tabs.active == "tab-ai"
        assert app.focused is settings.query_one("#source")
        await pilot.press("f3")
        await _settle(pilot)
        assert tabs.active == "tab-document"
        assert app.focused is settings.query_one("#writing_style")
        # All four Document buttons fit in 70 columns (Close was clipped).
        for button in settings.query("#document-buttons Button").results(Button):
            assert button.region.x + button.region.width <= 70, button.label
        await pilot.press("escape")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)


async def test_relaunch_resumes_at_the_last_cursor_position(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        area.load_text("one\n\ntwo\n\nthree")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = "resume"
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename == "resume.json"
        area.move_cursor((4, 2))
        await pilot.pause()
        assert "Section 3 of 3" in _text(editor.query_one("#section-info", Static))
        await pilot.press("ctrl+q")
        await _settle(pilot)
    assert Session.load().last_cursor == [4, 2]

    app2 = WritingAssistantApp(Session.load(), client_factory=app._client_factory)
    async with app2.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        editor = app2.screen
        assert isinstance(editor, EditorScreen)
        assert editor.filename == "resume.json"
        assert editor.query_one("#editor", TextArea).cursor_location == (4, 2)
        assert "Section 3 of 3" in _text(editor.query_one("#section-info", Static))
        # A different document starts at the top again.
        await pilot.press("ctrl+n")
        await _settle(pilot)
        app2.screen.query_one("#title", Input).value = "Other"
        await pilot.click("#create")
        await _settle(pilot)
        assert Session.load().last_cursor is None


async def test_register_mode_states_the_password_minimum(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        password = app.screen.query_one("#password", Input)
        assert "8 characters" not in password.placeholder
        await pilot.click("#toggle")
        await _settle(pilot)
        assert "at least 8 characters" in password.placeholder
        await pilot.click("#toggle")
        await _settle(pilot)
        assert "8 characters" not in password.placeholder


def test_help_text_covers_dialog_keys():
    for phrase in ("Esc", "F3 switches", "Ctrl+C", "PageUp", "several paragraphs"):
        assert phrase in HELP_TEXT, phrase


def test_main_help_names_the_session_file(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "tui_session.json" in out
    assert "WRITING_ASSISTANT_TUI_HOME" in out


async def test_ctrl_v_pastes_from_the_system_clipboard(tui_app, mocker):
    """Ctrl+V inserts text copied in another program, in the editor, the
    title, and the Settings fields; a Ctrl+C copy inside the app wins over
    the system clipboard until something else is copied."""
    app = tui_app
    clipboard = {"text": "from the desktop"}
    mocker.patch(
        "writing_assistant.tui.app.read_system_clipboard",
        side_effect=lambda: clipboard["text"],
    )
    written = mocker.patch(
        "writing_assistant.tui.app.write_system_clipboard", return_value=True
    )
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        text_area = editor.query_one("#editor", TextArea)
        text_area.focus()
        await pilot.press("ctrl+v")
        assert text_area.text == "from the desktop"

        editor.query_one("#title", Input).focus()
        await pilot.press("ctrl+v")
        assert editor.query_one("#title", Input).value == "from the desktop"

        # A copy made inside the app is mirrored to the system clipboard,
        # so the next paste returns it whether or not the terminal honours
        # OSC 52.
        text_area.focus()
        text_area.select_all()
        await pilot.press("ctrl+c")
        written.assert_called_with("from the desktop")

        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings, SettingsScreen)
        clipboard["text"] = "engineers"
        settings.query_one("#target_audience", Input).focus()
        await pilot.press("ctrl+v")
        assert settings.query_one("#target_audience", Input).value == "engineers"
        settings.query_one("#background_context", TextArea).focus()
        await pilot.press("ctrl+v")
        assert settings.query_one("#background_context", TextArea).text == "engineers"


async def test_ctrl_v_without_a_system_clipboard_uses_the_app_clipboard(
    tui_app, mocker
):
    app = tui_app
    mocker.patch("writing_assistant.tui.app.read_system_clipboard", return_value=None)
    mocker.patch("writing_assistant.tui.app.write_system_clipboard", return_value=False)
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        text_area = editor.query_one("#editor", TextArea)
        text_area.focus()
        await pilot.press("ctrl+v")  # nothing copied yet: no crash, no change
        assert text_area.text == ""
        text_area.load_text("copied inside")
        text_area.select_all()
        await pilot.press("ctrl+c")
        editor.query_one("#title", Input).focus()
        await pilot.press("ctrl+v")
        assert editor.query_one("#title", Input).value == "copied inside"


async def test_toggle_to_register_focuses_the_confirm_field(tui_app):
    """Switching to 'Create an account' must move focus to the new field, not
    leave it on the toggled button where a stray Enter flips the mode back."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        login = app.screen
        assert isinstance(login, LoginScreen)
        await pilot.click("#toggle")
        await _settle(pilot)
        assert app.focused is login.query_one("#confirm", Input)
        await pilot.click("#toggle")
        await _settle(pilot)
        assert app.focused is login.query_one("#password", Input)


async def test_login_f1_opens_help(tui_app):
    from writing_assistant.tui.app import MessageScreen

    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        assert isinstance(app.screen, LoginScreen)
        await pilot.press("f1")
        await _settle(pilot)
        assert isinstance(app.screen, MessageScreen)


def test_all_generation_modes_have_a_key_binding():
    """The README says adding a GENERATION_MODES entry gives the mode a key;
    the bindings are derived from that list so the two cannot drift."""
    from textual.binding import Binding

    from writing_assistant.tui.app import GENERATION_MODES

    bound = {b.key: b.action for b in EditorScreen.BINDINGS if isinstance(b, Binding)}
    for mode, _label, key in GENERATION_MODES:
        assert bound.get(key) == f"generate('{mode}')", mode


async def test_ai_settings_rejects_a_bad_server_url(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings, SettingsScreen)
        settings.query_one("#tabs").active = "tab-ai"
        await _settle(pilot)
        settings.query_one("#server_url", Input).value = "not-a-url"
        settings.query_one("#ai", Button).press()
        await _settle(pilot)
        # Validation failed: the dialog stays open on the AI tab.
        assert isinstance(app.screen, SettingsScreen)
        assert app.screen.query_one("#tabs").active == "tab-ai"
        # A proper URL saves and closes the dialog.
        settings.query_one("#server_url", Input).value = "http://localhost:11434"
        settings.query_one("#ai", Button).press()
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)


async def test_export_asks_before_overwriting_an_existing_file(tui_app, tmp_path):
    app = tui_app
    target = tmp_path / "out.json"
    target.write_text("OLD")
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("fresh content")
        await pilot.pause()
        editor.action_export()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = str(target)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.click("#cancel")  # decline the overwrite
        await _settle(pilot)
        assert target.read_text() == "OLD"
        # Export again and accept the overwrite this time.
        editor.action_export()
        await _settle(pilot)
        app.screen.query_one("#value", Input).value = str(target)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert "fresh content" in target.read_text()


async def test_copy_message_reflects_whether_a_clipboard_tool_exists(
    tui_app, monkeypatch
):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("body")
        await pilot.pause()
        notes: list[str] = []
        monkeypatch.setattr(editor, "notify", lambda msg, **k: notes.append(msg))
        monkeypatch.setattr(
            "writing_assistant.tui.app.system_clipboard_available", lambda: False
        )
        editor.action_copy()
        await pilot.pause()
        assert any("No clipboard tool" in m for m in notes)
        notes.clear()
        monkeypatch.setattr(
            "writing_assistant.tui.app.system_clipboard_available", lambda: True
        )
        editor.action_copy()
        await pilot.pause()
        assert any("copied to the clipboard" in m for m in notes)


async def test_generation_requested_while_another_runs_is_queued(tui_app, mocker):
    """A second F-key during a generation used to be dropped without a word."""
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        release = asyncio.Event()
        calls: list[str] = []

        async def slow_generate(fields):
            calls.append(fields["generation_mode"])
            if len(calls) == 1:
                await release.wait()
            return f"{fields['generation_mode']} of {fields['user_text']}"

        mocker.patch.object(editor.client, "generate_text", side_effect=slow_generate)
        area = editor.query_one("#editor", TextArea)
        area.load_text("First one.\n\nSecond one.")
        await pilot.pause()
        area.move_cursor((0, 2))
        await pilot.pause()
        await pilot.press("f5")
        await pilot.pause()
        status = editor.query_one("#section-status", Static)
        assert _text(status) == "Generating ideas…"

        # Move to the second section and ask for a rewrite while the first
        # request is still in flight.
        area.move_cursor((2, 2))
        await pilot.pause()
        assert _text(status) == "", "status must not leak from another section"
        await pilot.press("f6")
        await pilot.pause()
        assert _text(status) == "Queued: rewrite"
        assert "runs next" in _text(editor.query_one("#suggestion-text", Static))
        assert any("Queued rewrite" in str(n.message) for n in app._notifications)
        # Asking again for the same section does not queue it twice.
        await pilot.press("f7")
        await pilot.pause()
        assert len(editor._queue) == 1

        release.set()
        await _settle(pilot)
        assert calls == ["ideas", "rewrite"]
        assert editor.sections[0].generated_text == "ideas of First one."
        assert editor.sections[1].generated_text == "rewrite of Second one."
        assert _text(status) == ""
        assert "rewrite of Second one." in _text(
            editor.query_one("#suggestion-text", Static)
        )
        assert editor._active is None
        assert not editor._queue


async def test_unsaved_changes_prompt_can_save_and_continue(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("keep me")
        await pilot.pause()
        assert editor.dirty
        assert editor.filename is None
        editor.action_open()
        await _settle(pilot)
        assert isinstance(app.screen, UnsavedChangesScreen)
        await pilot.click("#save")
        await _settle(pilot)
        # Never saved: Save As asks for a name, then the Open picker follows.
        assert isinstance(app.screen, PromptScreen)
        app.screen.query_one("#value", Input).value = "kept"
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename == "kept.json"
        assert not editor.dirty
        assert isinstance(app.screen, PickerScreen)
        await pilot.press("escape")
        await _settle(pilot)

        # Saved before: Save stores it under the same name, no prompt.
        editor.query_one("#editor", TextArea).load_text("keep me too")
        await pilot.pause()
        editor.action_new()
        await _settle(pilot)
        assert isinstance(app.screen, UnsavedChangesScreen)
        await pilot.click("#save")
        await _settle(pilot)
        assert isinstance(app.screen, NewDocumentScreen)
        await pilot.press("escape")
        await _settle(pilot)
        data = await editor.client.load_document("kept.json")
        assert data["content"] == "keep me too"
        assert not editor.dirty

        # Cancel leaves everything as it was; Discard still discards.
        editor.query_one("#editor", TextArea).load_text("changed again")
        await pilot.pause()
        editor.action_open()
        await _settle(pilot)
        await pilot.click("#cancel")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)
        assert editor.dirty
        editor.action_open()
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert isinstance(app.screen, PickerScreen)


async def test_new_document_dialog_submits_on_enter_and_says_when_it_is_stored(
    tui_app,
):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.action_new()
        await _settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, NewDocumentScreen)
        assert str(dialog.query_one("#create", Button).label) == "Start Document"
        assert app.focused is dialog.query_one("#title", Input)
        await pilot.press(*"Notes", "enter")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)
        assert editor.title_input.value == "Notes"
        assert editor.filename is None
        assert any("Ctrl+S stores it" in str(n.message) for n in app._notifications), [
            n.message for n in app._notifications
        ]


async def test_use_suggestion_with_several_paragraphs_starts_at_the_first(
    tui_app, mocker
):
    mocker.patch(
        "writing_assistant.app.main.cb.new_paragraph",
        return_value="Alpha part.\n\nBeta part.\n\nGamma part.",
    )
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        area.load_text("Intro.\n\nMiddle.\n\nEnd.")
        await pilot.pause()
        area.move_cursor((2, 1))
        await pilot.pause()
        await pilot.press("f6")
        await _settle(pilot)
        await pilot.press("ctrl+u")
        await _settle(pilot)
        assert area.text == (
            "Intro.\n\nAlpha part.\n\nBeta part.\n\nGamma part.\n\nEnd."
        )
        assert len(editor.sections) == 5
        assert area.cursor_location == (2, 0)
        assert editor.current_index == 1
        assert "Section 2 of 5" in _text(editor.query_one("#section-info", Static))
        assert any("3 sections" in str(n.message) for n in app._notifications), [
            n.message for n in app._notifications
        ]


async def test_use_ideas_as_text_asks_first(tui_app, mocker):
    mocker.patch(
        "writing_assistant.app.main.cb.new_paragraph",
        return_value="- Say more.\n\n- Cite a source.",
    )
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        area.load_text("Some draft text.")
        await pilot.pause()
        await pilot.press("f5")
        await _settle(pilot)
        assert editor.sections[0].mode == "ideas"
        await pilot.press("ctrl+u")
        await _settle(pilot)
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.click("#cancel")
        await _settle(pilot)
        assert area.text == "Some draft text."
        await pilot.press("ctrl+u")
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert area.text == "- Say more.\n\n- Cite a source."
        # A rewrite of the same section replaces it without asking.
        await pilot.press("f6")
        await _settle(pilot)
        assert editor.sections[0].mode == "rewrite"
        await pilot.press("ctrl+u")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)


async def test_prompt_captions_wrap_inside_the_dialog(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.action_save_as()
        await _settle(pilot)
        dialog = app.screen
        assert isinstance(dialog, PromptScreen)
        caption = dialog.query_one(".prompt-label", Static)
        assert "Export for that)" in str(caption.content)
        assert caption.region.height >= 2, caption.region
        assert caption.region.width <= dialog.query_one(".dialog").region.width


async def test_settings_and_delete_messages_explain_the_editor_state(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("text")
        await pilot.pause()
        editor._save_as("doc.json", save_as=True)
        await _settle(pilot)
        assert not editor.dirty
        await pilot.press("f3")
        await _settle(pilot)
        # Opening Settings clears lingering toasts (the first-run hint).
        assert not list(app._notifications)
        settings = app.screen
        settings.query_one("#target_audience", Input).value = "students"
        settings.query_one("#default", Button).press()
        await _settle(pilot)
        messages = [str(n.message) for n in app._notifications]
        assert messages == [
            "Saved as your default settings and applied to this document."
        ], messages
        assert editor.dirty

        editor._mark_dirty(False)
        editor.action_delete()
        await _settle(pilot)
        await pilot.click("#confirm")
        await _settle(pilot)
        assert editor.filename is None
        assert editor.dirty
        assert editor.query_one("#editor", TextArea).text == "text"
        assert any(
            "stays in the editor" in str(n.message) for n in app._notifications
        ), [n.message for n in app._notifications]


def test_help_text_covers_editing_keys_and_the_save_choice():
    for needle in ("Ctrl+X", "Ctrl+Z", "Shift+Arrows", "Queued", "Save (save"):
        assert needle in HELP_TEXT, needle


# -- third first-use review: small terminals, long documents, big libraries --


async def _register_and_login_small(pilot, app: WritingAssistantApp) -> EditorScreen:
    """Register from the keyboard: on a short terminal the login box scrolls."""
    app.screen.query_one("#toggle", Button).press()
    await _settle(pilot)
    app.screen.query_one("#email", Input).value = EMAIL
    app.screen.query_one("#password", Input).value = PASSWORD
    confirm = app.screen.query_one("#confirm", Input)
    confirm.value = PASSWORD
    confirm.focus()
    await pilot.press("enter")
    await _settle(pilot)
    assert isinstance(app.screen, EditorScreen), _login_message(app)
    return app.screen


async def test_settings_dialog_is_usable_at_the_minimum_terminal_size(tui_app):
    """At 60x16 the dialog showed only its title and tab bar: no fields."""
    app = tui_app
    async with app.run_test(size=(60, 16)) as pilot:
        await _register_and_login_small(pilot, app)
        await pilot.press("f3")
        await _settle(pilot)
        settings = app.screen
        assert isinstance(settings, SettingsScreen)
        await pilot.press("f3")  # AI Settings tab
        await _settle(pilot)
        source = settings.query_one("#source")
        assert source.region.height > 0, "the AI source field is not on screen"
        assert source.region.y >= 0
        assert source.region.bottom <= 16, source.region
        test_button = settings.query_one("#test", Button)
        assert test_button.region.height > 0
        assert test_button.region.bottom <= 16, test_button.region
        # Tabbing reaches the fields below the fold too.
        settings.query_one("#model", Input).focus()
        await pilot.press("tab")
        await _settle(pilot)
        url = settings.query_one("#server_url", Input)
        assert app.focused is url
        assert url.region.height > 0
        assert url.region.bottom <= 16, url.region


async def test_file_menu_scrolls_on_a_short_terminal(tui_app):
    """The menu was clipped at 60x16: Enter ran a hidden 'Log out'."""
    app = tui_app
    async with app.run_test(size=(60, 16)) as pilot:
        await _register_and_login_small(pilot, app)
        await pilot.press("f2")
        await _settle(pilot)
        menu = app.screen.query_one("#menu")
        assert menu.region.bottom <= 16, menu.region
        await pilot.press("end")
        await _settle(pilot)
        last = menu.get_option_at_index(menu.option_count - 1)
        assert menu.highlighted == menu.option_count - 1
        assert last.id == "logout"
        # The list scrolled so the highlighted entry is within its viewport.
        assert menu.scroll_offset.y > 0
        await pilot.press("escape")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)


async def test_open_picker_filters_as_you_type(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        for name, title in (("one", "Alpha notes"), ("two", "Beta draft")):
            await editor.client.save_document(
                f"{name}.json", {"title": title, "content": "x", "sections": []}
            )
        await pilot.press("ctrl+o")
        await _settle(pilot)
        picker = app.screen
        assert isinstance(picker, PickerScreen)
        options = picker.query_one("#entries")
        assert options.option_count == 2
        picker.query_one("#filter", Input).focus()
        await pilot.press(*"beta")
        await _settle(pilot)
        assert options.option_count == 1
        assert options.get_option_at_index(0).id == "two.json"
        # Down/Up from the filter field move the list; Enter opens.
        await pilot.press("down", "up", "enter")
        await _settle(pilot)
        assert isinstance(app.screen, EditorScreen)
        assert editor.filename == "two.json"
        assert editor.title_input.value == "Beta draft"


async def test_cursor_offset_and_panel_redraw_on_long_documents(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        area = editor.query_one("#editor", TextArea)
        text = "\n\n".join(f"Paragraph {i} with some words." for i in range(40))
        area.load_text(text)
        area.focus()
        await pilot.pause()
        area.move_cursor((6, 4))  # inside "Paragraph 3"
        await _settle(pilot)
        expected = sum(len(line) + 1 for line in text.split("\n")[:6]) + 4
        assert editor._cursor_offset() == expected
        assert editor.current_index == 3
        assert _text(editor.query_one("#section-info", Static)) == "Section 4 of 40"
        # Moving within the same section leaves the panel alone.
        shown = editor._panel_shown
        area.move_cursor((6, 10))
        await _settle(pilot)
        assert editor._panel_shown is shown
        # Moving to another section redraws it.
        area.move_cursor((8, 0))
        await _settle(pilot)
        assert editor._panel_shown is not shown
        assert _text(editor.query_one("#section-info", Static)) == "Section 5 of 40"


async def test_test_connection_result_is_not_also_a_toast(tui_app, mocker):
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
        assert "Could not connect" in _text(
            settings.query_one("#connection-status", Static)
        )
        assert not any(
            "Could not connect" in str(n.message) for n in app._notifications
        )


async def test_successful_save_clears_a_stale_connection_error(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        editor = await _register_and_login(pilot, app)
        editor.query_one("#editor", TextArea).load_text("Some text.")
        await pilot.pause()
        panel = editor.query_one("#suggestion-text", Static)
        panel.update("Error: Could not connect to the writing-assistant server")
        editor._panel_shown = None
        assert await editor._save_document("back.json", save_as=True)
        await _settle(pilot)
        assert "Error:" not in _text(panel)


async def test_command_palette_offers_only_relevant_system_commands(tui_app):
    app = tui_app
    async with app.run_test(size=SIZE) as pilot:
        await _register_and_login(pilot, app)
        titles = {c.title for c in app.get_system_commands(app.screen)}
        assert titles == {"Quit", "Keys"}


def test_help_text_covers_the_palette_and_the_open_filter():
    for needle in ("Ctrl+P", "filter"):
        assert needle in HELP_TEXT, needle
