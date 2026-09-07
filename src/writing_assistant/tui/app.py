"""The writing-assistant terminal application (Textual).

Layout, top to bottom: a header strip (document name, user), the title
field, the document editor, and a suggestion panel with the four generation
modes. Every operation the web interface offers is reachable from the File
menu (F2), the Settings dialog (F3), or a key binding listed in the footer.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, ClassVar, cast

from textual import on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding, BindingType
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.document._document import Document
from textual.events import Key, Resize
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.option_list import Option

from .client import ApiError, AuthError, WritingAssistantClient
from .clipboard import (
    read_system_clipboard,
    system_clipboard_available,
    write_system_clipboard,
)
from .sections import (
    Section,
    parse_sections,
    restore_saved_sections,
    section_index_at,
)
from .session import Session

WRITING_STYLES = [
    ("Formal", "formal"),
    ("Casual", "casual"),
    ("Academic", "academic"),
    ("Creative", "creative"),
    ("Technical", "technical"),
    ("Persuasive", "persuasive"),
]
TONES = [
    ("Neutral", "neutral"),
    ("Professional", "professional"),
    ("Friendly", "friendly"),
    ("Authoritative", "authoritative"),
    ("Conversational", "conversational"),
    ("Enthusiastic", "enthusiastic"),
]
AI_SOURCES = [
    ("Server default", ""),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Ollama", "ollama"),
]
# Plain-text labels on purpose: emoji render at unpredictable widths in
# terminals (and not at all over some SSH/tmux setups), which breaks layout.
GENERATION_MODES = [
    ("ideas", "Ideas", "f5"),
    ("rewrite", "Rewrite", "f6"),
    ("improve", "Improve", "f7"),
    ("proofread", "Proofread", "f8"),
]

DEFAULT_METADATA: dict[str, Any] = {
    "writing_style": "formal",
    "target_audience": "",
    "tone": "neutral",
    "background_context": "",
    "generation_directive": "",
    "word_limit": None,
    "source": "",
    "model": "",
}
# The fields a quick-access template stores: the writing settings, not the
# AI source/model (those say where to generate, not how to write).
TEMPLATE_KEYS = (
    "writing_style",
    "target_audience",
    "tone",
    "background_context",
    "generation_directive",
    "word_limit",
)


def template_summary(settings: dict[str, Any]) -> str:
    """A one-line description of a template's settings for lists."""
    parts = [
        str(settings.get("writing_style") or "formal"),
        str(settings.get("tone") or "neutral"),
    ]
    if settings.get("target_audience"):
        parts.append(f"for {settings['target_audience']}")
    if settings.get("word_limit"):
        parts.append(f"~{settings['word_limit']} words")
    return " · ".join(parts)


HELP_TEXT = """\
[b]Writing Assistant — keyboard reference[/b]

[b]Editing[/b]
  Type in the editor; leave a blank line between sections (paragraphs).
  The suggestion panel follows the section under the cursor.
  Tab / Shift+Tab move between the title, the editor, the suggestion
  panel (arrow keys scroll it) and the buttons.
  Shift+Arrows select text; Ctrl+X cuts it; Ctrl+Z / Ctrl+Y undo / redo.
  To move a section: select it (Shift+Down from its first line), Ctrl+X,
  put the cursor on the blank line where it should go, Ctrl+V. To delete
  one, select it and press Delete.
  Ctrl+C copies the selection; Ctrl+V pastes (from the system clipboard
  when wl-paste, xclip, xsel or pbpaste is installed — otherwise, e.g.
  over SSH, use the terminal's own paste: Ctrl+Shift+V, Shift+Insert, or
  Shift+middle-click). The same works in every dialog field.

[b]AI suggestions[/b] (for the section under the cursor)
  F5      Ideas (also Ctrl+G)
  F6      Rewrite
  F7      Improve
  F8      Proofread
  Ctrl+U  Use the suggestion as the section text
  (A suggestion with several paragraphs becomes several sections; the
  cursor lands on the first of them. Ideas are advice rather than prose,
  so using them as text asks first.)
  A suggestion requested while another is still generating is queued and
  runs next; the panel says "Queued" for that section meanwhile.

[b]Documents[/b]
  F2      File menu: New, Save, Save As, Open, Delete, Create snapshot,
          Revert to snapshot, Import, Export, Copy, Account (email,
          password), Log out
  Ctrl+S  Save
  Ctrl+O  Open
  Ctrl+N  New (a title and optional outline; Ctrl+S then stores it in
          your library)
  F3      Settings: writing style, tone, audience, context, directive,
          word limit; AI source/model, connection, environment variables
  F4      Templates: start a new document from a saved set of writing
          settings (an "Email" template, say). The open document is saved
          first when it has a name; otherwise you are asked. Create
          templates in Settings → Document → Save as Template.
  F1      This help
  Ctrl+P  Command palette: type part of a command's name (Save As, Create
          snapshot, Export, Log out, …) and press Enter to run it
  Ctrl+Q  Quit (asks first if there are unsaved changes)
  Ctrl+C  Copies the selection in the editor; it does not quit

[b]Dialogs[/b]
  Esc         Close any dialog or menu without changes
  Enter       Confirm (or open a dropdown, then Up/Down and Enter)
  "Unsaved changes" prompts offer Save (save, then continue), Discard
  changes, and Cancel.
  Tab         Next field; Shift+Tab previous
  In Settings, F3 switches between the Document and AI Settings tabs
  (so do Left/Right while the tab bar is focused).
  In the Open dialog, type to filter the list by name or title; Up/Down
  move through the matches and Enter opens the highlighted one.
  Long dialogs such as this one scroll: Up/Down, PageUp/PageDown.

On a short terminal (fewer than 22 rows) the mode buttons are hidden to
keep the suggestion panel on screen; the keys above still work.

Documents are stored on the writing-assistant server, in the same per-user
library the web interface uses, so you can switch between the two freely.
"""


# --------------------------------------------------------------------------
# Small reusable modals
# --------------------------------------------------------------------------


def _fit_option_list(options: OptionList, screen_height: int, overhead: int) -> None:
    """Cap ``options`` so the dialog around it fits in ``screen_height`` rows.

    The dialog is ``height: auto`` and clips whatever does not fit, so on a
    short terminal a list longer than the screen lost its last entries —
    the highlight moved into the clipped part and Enter ran an item the
    user never saw. Capped, the list scrolls to keep the highlight visible.
    ``overhead`` is the number of rows the dialog uses around the list.
    """
    options.styles.max_height = max(3, screen_height - overhead)


class MessageScreen(ModalScreen[None]):
    """A scrollable text dialog with a single OK button."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "dismiss", "Close")]

    def __init__(self, title: str, body: str, *, markup: bool = True) -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._markup = markup

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog-wide dialog-message"):
            yield Label(self._title, classes="dialog-title")
            with VerticalScroll(classes="dialog-body"):
                yield Static(self._body, markup=self._markup)
            with Horizontal(classes="dialog-buttons"):
                yield Button("OK", variant="primary", id="ok")

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self, title: str, message: str, *, confirm_label: str = "Confirm"
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            yield Static(self._message, classes="dialog-body")
            with Horizontal(classes="dialog-buttons"):
                yield Button(self._confirm_label, variant="error", id="confirm")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#confirm")
    def _confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)


class UnsavedChangesScreen(ModalScreen[str]):
    """Save / discard / cancel before an action that would drop the editor text.

    Dismisses with ``"save"``, ``"discard"`` or ``"cancel"``. The Discard
    button keeps the ``confirm`` id so it sits where ConfirmScreen's does.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, what: str) -> None:
        super().__init__()
        self._what = what

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Unsaved changes", classes="dialog-title")
            yield Static(
                f"The current document has unsaved changes. {self._what} anyway?",
                classes="dialog-body",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Discard changes", variant="error", id="confirm")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#save")
    def _save(self) -> None:
        self.dismiss("save")

    @on(Button.Pressed, "#confirm")
    def _discard(self) -> None:
        self.dismiss("discard")

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss("cancel")


class PromptScreen(ModalScreen[str | None]):
    """Ask for a single line of text (filename, path)."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        label: str,
        *,
        default: str = "",
        placeholder: str = "",
        confirm_label: str = "OK",
    ) -> None:
        super().__init__()
        self._title = title
        self._label = label
        self._default = default
        self._placeholder = placeholder
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._title, classes="dialog-title")
            # Static rather than Label: a caption longer than the dialog is
            # wrapped instead of cut off at the border.
            yield Static(self._label, classes="prompt-label")
            yield Input(value=self._default, placeholder=self._placeholder, id="value")
            with Horizontal(classes="dialog-buttons"):
                yield Button(self._confirm_label, variant="primary", id="confirm")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#value", Input).focus()

    @on(Input.Submitted, "#value")
    @on(Button.Pressed, "#confirm")
    def _confirm(self) -> None:
        value = self.query_one("#value", Input).value.strip()
        self.dismiss(value or None)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class AccountScreen(ModalScreen[list[str]]):
    """The logged-in user's account: email address and password.

    One dialog for both, with a single current-password field, since the
    server requires the current password for either change. Talks to the
    server itself (like LoginScreen) so a refusal — wrong current
    password, address in use, new password too short — keeps the dialog
    open with the reason rather than making the user start over.

    The email is changed first, then the password; a refused password
    does not undo an email change that already went through, so the
    dialog updates ``session.email`` itself as soon as the server accepts
    the address. Dismisses with the list of what changed (``"email"``,
    ``"password"``), empty when cancelled before anything was applied.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, client: Any, session: Session) -> None:
        super().__init__()
        self._client = client
        self._session = session
        self._changed: list[str] = []

    def compose(self) -> ComposeResult:
        email = self._session.email or ""
        with Vertical(classes="dialog"):
            yield Label("Account", classes="dialog-title")
            yield Static(f"Signed in as {email}", id="signed-in")
            yield Label("Email")
            yield Input(value=email, placeholder="you@example.com", id="email")
            yield Label("Current password (required for any change)")
            yield Input(password=True, id="current")
            yield Label("New password (leave blank to keep the current one)")
            yield Input(placeholder="at least 8 characters", password=True, id="new")
            yield Label("Confirm new password")
            yield Input(placeholder="repeat new password", password=True, id="confirm")
            yield Static("", id="message", classes="status-line")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Apply", variant="primary", id="apply")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#email", Input).focus()

    def _set_message(self, text: str, *, error: bool = False) -> None:
        widget = self.query_one("#message", Static)
        widget.update(text)
        widget.set_classes("status-line error" if error else "status-line")

    def _fail(self, text: str, focus: str) -> None:
        self._set_message(text, error=True)
        self.query_one("#apply", Button).disabled = False
        self.query_one(focus, Input).focus()

    @on(Input.Submitted)
    @on(Button.Pressed, "#apply")
    def _submit(self) -> None:
        email = self.query_one("#email", Input).value.strip()
        current = self.query_one("#current", Input).value
        new = self.query_one("#new", Input).value
        confirm = self.query_one("#confirm", Input).value
        if not email:
            self._fail("Enter an email address.", "#email")
            return
        if not current:
            self._fail("Enter your current password.", "#current")
            return
        if new != confirm:
            self._fail("The new passwords do not match.", "#confirm")
            return
        new_email = email if email != (self._session.email or "") else None
        if new_email is None and not new:
            self._fail(
                "Nothing to change: edit the email or enter a new password.", "#email"
            )
            return
        self.query_one("#apply", Button).disabled = True
        self._set_message("Contacting server...")
        self._apply(new_email, current, new or None)

    @work(exclusive=True)
    async def _apply(
        self, new_email: str | None, current: str, new: str | None
    ) -> None:
        if new_email is not None:
            try:
                stored = await self._client.change_email(current, new_email)
            except ApiError as exc:
                self._fail(exc.message, "#email")
                return
            self._session.email = stored
            self._session.save()
            self._changed.append("email")
            self.query_one("#signed-in", Static).update(f"Signed in as {stored}")
            self.query_one("#email", Input).value = stored
        if new is not None:
            try:
                await self._client.change_password(current, new)
            except ApiError as exc:
                self._fail(exc.message, "#new")
                return
            self._changed.append("password")
        self.dismiss(list(self._changed))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(list(self._changed))


class MenuScreen(ModalScreen[str | None]):
    """A vertical menu of actions; returns the chosen action id."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, items: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._items = items

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog-menu"):
            yield Label(self._title, classes="dialog-title")
            yield OptionList(
                *[Option(label, id=item_id) for item_id, label in self._items],
                id="menu",
            )

    def on_mount(self) -> None:
        self.query_one("#menu", OptionList).focus()

    def on_resize(self, event: Resize) -> None:
        # Border + padding (4), title and its margin (2), a spare row.
        _fit_option_list(self.query_one("#menu", OptionList), event.size.height, 7)

    @on(OptionList.OptionSelected, "#menu")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PickerScreen(ModalScreen[tuple[str, str] | None]):
    """Pick one entry from a list, with optional secondary actions.

    Returns ``(action, entry_id)`` where ``action`` is ``"open"`` or one of
    the extra button ids, or ``None`` when cancelled.
    """

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        entries: list[tuple[str, str]],
        *,
        empty_message: str = "Nothing here yet.",
        open_label: str = "Open",
        extra_buttons: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._entries = entries
        self._empty_message = empty_message
        self._open_label = open_label
        self._extra_buttons = extra_buttons or []

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog-wide"):
            yield Label(self._title, classes="dialog-title")
            if self._entries:
                # Typing narrows a long library down; Up/Down and Enter
                # still work from the filter field (see on_key).
                yield Input(
                    placeholder="Type to filter…",
                    id="filter",
                    classes="picker-filter",
                )
                yield OptionList(
                    *[Option(label, id=entry_id) for entry_id, label in self._entries],
                    id="entries",
                )
            else:
                yield Static(self._empty_message, classes="dialog-body muted")
            with Horizontal(classes="dialog-buttons"):
                if self._entries:
                    yield Button(self._open_label, variant="primary", id="open")
                    for button_id, label in self._extra_buttons:
                        yield Button(label, id=button_id)
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self._entries:
            self.query_one("#entries", OptionList).focus()

    def on_resize(self, event: Resize) -> None:
        if self._entries:
            # Border + padding (4), title (2), filter (4), buttons (4).
            _fit_option_list(
                self.query_one("#entries", OptionList), event.size.height, 14
            )

    @on(Input.Changed, "#filter")
    def _filter_changed(self, event: Input.Changed) -> None:
        needle = event.value.strip().lower()
        options = self.query_one("#entries", OptionList)
        options.clear_options()
        options.add_options(
            [
                Option(label, id=entry_id)
                for entry_id, label in self._entries
                if needle in label.lower()
            ]
        )
        if options.option_count:
            options.highlighted = 0

    @on(Input.Submitted, "#filter")
    def _filter_submitted(self) -> None:
        entry_id = self._highlighted_id()
        if entry_id is not None:
            self.dismiss(("open", entry_id))

    def on_key(self, event: Key) -> None:
        # Arrow keys in the filter field move the list's highlight, so a
        # user need not Tab to the list after narrowing it down.
        if not isinstance(self.focused, Input) or self.focused.id != "filter":
            return
        options = self.query_one("#entries", OptionList)
        actions = {
            "up": options.action_cursor_up,
            "down": options.action_cursor_down,
            "pageup": options.action_page_up,
            "pagedown": options.action_page_down,
        }
        action = actions.get(event.key)
        if action is not None:
            event.stop()
            event.prevent_default()
            action()

    def _highlighted_id(self) -> str | None:
        options = self.query_one("#entries", OptionList)
        index = options.highlighted
        if index is None:
            return None
        option_id = options.get_option_at_index(index).id
        return str(option_id) if option_id is not None else None

    @on(OptionList.OptionSelected, "#entries")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(("open", str(event.option.id)))

    @on(Button.Pressed)
    def _button(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "cancel":
            self.dismiss(None)
            return
        entry_id = self._highlighted_id()
        if entry_id is None:
            self.notify("Select an entry first.", severity="warning")
            return
        self.dismiss((button_id, entry_id))

    def action_cancel(self) -> None:
        self.dismiss(None)


class NewDocumentScreen(ModalScreen[tuple[str, str] | None]):
    """Title plus an optional initial outline for a new document."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog-wide"):
            yield Label("New Document", classes="dialog-title")
            yield Label("Title")
            yield Input(placeholder="Enter document title...", id="title")
            yield Label("Initial content (optional — blank lines separate sections)")
            yield TextArea(id="outline", classes="dialog-textarea")
            yield Static(
                "The document is stored in your library when you press Ctrl+S.",
                classes="muted",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Start Document", variant="success", id="create")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#title", Input).focus()

    # Enter in the title field submits, as it does in the other dialogs.
    @on(Input.Submitted, "#title")
    @on(Button.Pressed, "#create")
    def _create(self) -> None:
        title = self.query_one("#title", Input).value.strip()
        outline = self.query_one("#outline", TextArea).text
        self.dismiss((title, outline))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


# --------------------------------------------------------------------------
# Settings dialog
# --------------------------------------------------------------------------


def _env_vars_to_text(env_vars: dict[str, Any]) -> str:
    return "\n".join(f"{key}={value}" for key, value in env_vars.items())


def parse_env_vars_text(text: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines (blank lines and ``#`` comments ignored)."""
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Expected KEY=VALUE, got: {line!r}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Missing variable name in: {line!r}")
        result[key] = value.strip()
    return result


class SettingsScreen(ModalScreen[dict[str, Any] | None]):
    """Document metadata and AI settings, mirroring the web Settings dialog.

    Dismisses with ``{"action": ..., "metadata": ..., "ai": ...}`` where
    ``action`` is ``"document"`` (apply to this document), ``"default"``
    (also save as the user's server-side defaults), ``"ai"`` (save AI
    settings as defaults) or ``None`` when cancelled.
    """

    # F3 opened the dialog, so F3 again is the natural "other tab" key for
    # someone working from the keyboard (Textual's own way — Left/Right on
    # the focused tab bar — is not discoverable).
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("f3", "next_tab", "Switch tab", priority=True),
    ]

    def __init__(
        self,
        metadata: dict[str, Any],
        ai: dict[str, Any],
        *,
        allow_custom_env_vars: bool,
        editor: EditorScreen,
        templates: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__()
        self._metadata = dict(metadata)
        self._ai = dict(ai)
        self._allow_custom_env_vars = allow_custom_env_vars
        self._editor = editor
        self._templates: list[dict[str, Any]] = list(templates or [])

    def _template_options(self) -> list[tuple[str, int]]:
        return [(str(t["name"]), int(t["id"])) for t in self._templates]

    def _selected_template(self) -> dict[str, Any] | None:
        value = self.query_one("#template", Select).value
        if value is Select.BLANK:
            return None
        return next((t for t in self._templates if t.get("id") == value), None)

    def compose(self) -> ComposeResult:
        m = self._metadata
        ai = self._ai
        with Vertical(classes="dialog dialog-settings"):
            yield Label("Settings", classes="dialog-title")
            yield Static(
                "F3 switches tabs · Tab moves between fields · Esc closes",
                classes="dialog-hint",
            )
            with TabbedContent(id="tabs"):
                with (
                    TabPane("Document", id="tab-document"),
                    VerticalScroll(can_focus=False),
                ):
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-col"):
                            yield Label("Writing style")
                            yield Select(
                                WRITING_STYLES,
                                value=m.get("writing_style") or "formal",
                                allow_blank=False,
                                id="writing_style",
                            )
                        with Vertical(classes="form-col"):
                            yield Label("Tone")
                            yield Select(
                                TONES,
                                value=m.get("tone") or "neutral",
                                allow_blank=False,
                                id="tone",
                            )
                    yield Label("Target audience")
                    yield Input(
                        value=m.get("target_audience") or "",
                        placeholder="e.g., general public, experts, students...",
                        id="target_audience",
                    )
                    yield Label("Background context")
                    yield TextArea(
                        m.get("background_context") or "",
                        id="background_context",
                        classes="dialog-textarea small",
                    )
                    yield Label("Generation directive")
                    yield TextArea(
                        m.get("generation_directive") or "",
                        id="generation_directive",
                        classes="dialog-textarea small",
                    )
                    yield Label("Word limit (approximate words per section)")
                    yield Input(
                        value=str(m.get("word_limit") or ""),
                        placeholder="e.g., 100, 500, 1000",
                        id="word_limit",
                        type="integer",
                    )
                    yield Label("Quick-access templates", classes="section-heading")
                    yield Static(
                        "Apply a template to fill in the fields above, or save "
                        "the fields under a name to reuse them. F4 in the editor "
                        "starts a new document from a template.",
                        classes="muted",
                    )
                    with Horizontal(classes="form-row template-row"):
                        yield Select(
                            self._template_options(),
                            prompt="Apply a template…",
                            id="template",
                        )
                        yield Button("Save as Template", id="save-template")
                        yield Button("Delete", id="delete-template")
                with (
                    TabPane("AI Settings", id="tab-ai"),
                    VerticalScroll(can_focus=False),
                ):
                    with Horizontal(classes="form-row"):
                        with Vertical(classes="form-col"):
                            yield Label("AI source")
                            yield Select(
                                AI_SOURCES,
                                value=ai.get("source") or "",
                                allow_blank=False,
                                id="source",
                            )
                        with Vertical(classes="form-col"):
                            yield Label("Model")
                            yield Input(
                                value=ai.get("model") or "",
                                placeholder="e.g., gpt-4o, claude-sonnet-4-5, llama3.1:8b",
                                id="model",
                            )
                    if self._allow_custom_env_vars:
                        yield Label("Connection", classes="section-heading")
                        yield Static(
                            "Applies to whichever AI source is selected above. "
                            "Leave blank to use the server's configuration.",
                            classes="muted",
                        )
                        yield Label("Server URL")
                        yield Input(
                            value=ai.get("server_url") or "",
                            placeholder="e.g., http://localhost:11434 or https://api.example.com/v1",
                            id="server_url",
                        )
                        yield Label("API key")
                        yield Input(
                            value=ai.get("api_key") or "",
                            placeholder="e.g., sk-... (not needed for Ollama)",
                            password=True,
                            id="api_key",
                        )
                        yield Label("Environment variables", classes="section-heading")
                        yield Static(
                            "One KEY=VALUE per line, applied to each generation request.",
                            classes="muted",
                        )
                        yield TextArea(
                            _env_vars_to_text(ai.get("environment_variables") or {}),
                            id="environment_variables",
                            classes="dialog-textarea small",
                        )
                    else:
                        yield Static(
                            "Connection settings are managed by the server "
                            "administrator (custom environment variables are "
                            "disabled on this server).",
                            classes="muted",
                        )
            # Outside the scrolling form so a Test Connection result is
            # always on screen, next to the button that produced it.
            yield Static("", id="connection-status", classes="status-line hidden")
            with Horizontal(classes="dialog-buttons", id="document-buttons"):
                yield Button("Save to Document", variant="primary", id="document")
                yield Button("Save as Default", variant="success", id="default")
                yield Button("Reset", id="reset")
                yield Button("Close", id="cancel")
            with Horizontal(classes="dialog-buttons hidden", id="ai-buttons"):
                yield Button("Test Connection", id="test")
                yield Button("Save AI Settings", variant="primary", id="ai")
                yield Button("Close", id="cancel-ai")

    # -- collecting values -----------------------------------------------------

    COMPACT_ROWS: ClassVar[int] = 24

    def on_resize(self, event: Resize) -> None:
        self.query_one(".dialog-settings").set_class(
            event.size.height < self.COMPACT_ROWS, "compact"
        )

    def _value(self, widget_id: str) -> str:
        try:
            widget = self.query_one(f"#{widget_id}")
        except Exception:
            return ""
        if isinstance(widget, Select):
            value = widget.value
            return "" if value is Select.BLANK else str(value)
        if isinstance(widget, Input):
            return widget.value.strip()
        if isinstance(widget, TextArea):
            return widget.text.strip()
        return ""

    def collect_metadata(self) -> dict[str, Any]:
        word_limit_text = self._value("word_limit")
        word_limit: int | None = None
        if word_limit_text:
            try:
                word_limit = int(word_limit_text)
            except ValueError:
                word_limit = None
        return {
            "writing_style": self._value("writing_style") or "formal",
            "target_audience": self._value("target_audience"),
            "tone": self._value("tone") or "neutral",
            "background_context": self._value("background_context"),
            "generation_directive": self._value("generation_directive"),
            "word_limit": word_limit,
            "source": self._value("source"),
            "model": self._value("model"),
        }

    def collect_ai(self) -> dict[str, Any]:
        env_vars: dict[str, str] = {}
        server_url = self._value("server_url")
        if self._allow_custom_env_vars:
            env_vars = parse_env_vars_text(self._value("environment_variables"))
            if server_url and not server_url.startswith(("http://", "https://")):
                raise ValueError(
                    "Server URL must start with http:// or https:// "
                    f"(got {server_url!r})."
                )
        return {
            "source": self._value("source"),
            "model": self._value("model"),
            "server_url": server_url,
            "api_key": self._value("api_key"),
            "environment_variables": env_vars,
        }

    def _collect(self) -> dict[str, Any] | None:
        try:
            ai = self.collect_ai()
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            self.query_one("#tabs", TabbedContent).active = "tab-ai"
            return None
        return {"metadata": self.collect_metadata(), "ai": ai}

    # -- buttons -------------------------------------------------------------

    @on(Button.Pressed, "#document")
    @on(Button.Pressed, "#default")
    @on(Button.Pressed, "#ai")
    def _save(self, event: Button.Pressed) -> None:
        values = self._collect()
        if values is None:
            return
        values["action"] = event.button.id
        self.dismiss(values)

    def _fill_writing_fields(self, settings: dict[str, Any]) -> None:
        self.query_one("#writing_style", Select).value = (
            settings.get("writing_style") or "formal"
        )
        self.query_one("#tone", Select).value = settings.get("tone") or "neutral"
        self.query_one("#target_audience", Input).value = str(
            settings.get("target_audience") or ""
        )
        self.query_one("#background_context", TextArea).text = str(
            settings.get("background_context") or ""
        )
        self.query_one("#generation_directive", TextArea).text = str(
            settings.get("generation_directive") or ""
        )
        self.query_one("#word_limit", Input).value = str(
            settings.get("word_limit") or ""
        )

    @on(Button.Pressed, "#reset")
    def _reset(self) -> None:
        self._fill_writing_fields(DEFAULT_METADATA)
        self.query_one("#template", Select).clear()
        self.notify("Document settings reset to defaults (not yet saved).")

    # -- quick-access templates ---------------------------------------------------

    @on(Select.Changed, "#template")
    def _template_chosen(self) -> None:
        template = self._selected_template()
        if template is None:
            return
        self._fill_writing_fields(template.get("settings") or {})
        self.notify(
            f'Template "{template["name"]}" applied to the form — Save to '
            "Document keeps it."
        )

    async def _refresh_templates(self) -> bool:
        """Reload the template list from the server into the dropdown."""
        try:
            self._templates = await self._editor.client.list_templates()
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return False
        self._editor.templates = self._templates
        self.query_one("#template", Select).set_options(self._template_options())
        return True

    @on(Button.Pressed, "#save-template")
    def _save_template_pressed(self) -> None:
        self._save_template()

    @on(Button.Pressed, "#delete-template")
    def _delete_template_pressed(self) -> None:
        self._delete_template()

    @work
    async def _save_template(self) -> None:
        selected = self._selected_template()
        name = await self.app.push_screen_wait(
            PromptScreen(
                "Save as Template",
                "Name for these writing settings. Choosing an existing name "
                "replaces that template.",
                default=str(selected["name"]) if selected else "",
                placeholder="e.g., Email",
                confirm_label="Save",
            )
        )
        if not name:
            return
        existing = next((t for t in self._templates if t.get("name") == name), None)
        if existing is not None and existing is not selected:
            confirmed = await self.app.push_screen_wait(
                ConfirmScreen(
                    "Replace template",
                    f'A template named "{name}" already exists. Replace its '
                    "settings with the fields on this form?",
                    confirm_label="Replace",
                )
            )
            if not confirmed:
                return
        metadata = self.collect_metadata()
        settings = {key: metadata[key] for key in TEMPLATE_KEYS}
        try:
            message = await self._editor.client.save_template(name, settings)
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        if await self._refresh_templates():
            self.notify(f"{message}: {name}. Press F4 in the editor to use it.")

    @work
    async def _delete_template(self) -> None:
        template = self._selected_template()
        if template is None:
            self.notify("Choose a template to delete first.", severity="warning")
            return
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(
                "Delete template",
                f'Delete the template "{template["name"]}"? Documents that used '
                "it keep their settings.",
                confirm_label="Delete",
            )
        )
        if not confirmed:
            return
        try:
            message = await self._editor.client.delete_template(int(template["id"]))
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        if await self._refresh_templates():
            self.notify(message)

    @on(Button.Pressed, "#cancel")
    @on(Button.Pressed, "#cancel-ai")
    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_next_tab(self) -> None:
        tabs = self.query_one("#tabs", TabbedContent)
        tabs.active = "tab-ai" if tabs.active == "tab-document" else "tab-document"
        # Land on the first field of the new tab, as Tab from the bar would.
        first = "#source" if tabs.active == "tab-ai" else "#writing_style"
        self.query_one(first).focus()

    @on(TabbedContent.TabActivated, "#tabs")
    def _tab_changed(self, event: TabbedContent.TabActivated) -> None:
        ai_tab = event.pane.id == "tab-ai"
        self.query_one("#document-buttons").set_class(ai_tab, "hidden")
        self.query_one("#ai-buttons").set_class(not ai_tab, "hidden")
        self.query_one("#connection-status").set_class(not ai_tab, "hidden")

    @on(Select.Changed, "#source")
    @on(Input.Changed, "#model")
    @on(Input.Changed, "#server_url")
    @on(Input.Changed, "#api_key")
    def _clear_status(self) -> None:
        # A stale "connected" only vouched for the values it was run with.
        self.query_one("#connection-status", Static).update("")

    @on(Button.Pressed, "#test")
    def _test(self) -> None:
        values = self._collect()
        if values is None:
            return
        status = self.query_one("#connection-status", Static)
        status.update("Testing connection...")
        status.set_classes("status-line")
        self._run_test(values["ai"])

    @work(exclusive=True)
    async def _run_test(self, ai: dict[str, Any]) -> None:
        status = self.query_one("#connection-status", Static)
        try:
            report = await self._editor.client.test_connection(
                {
                    "source": ai["source"],
                    "model": ai["model"],
                    "server_url": ai["server_url"],
                    "api_key": ai["api_key"],
                    "environment_variables": json.dumps(ai["environment_variables"]),
                }
            )
        except ApiError as exc:
            status.update(f"✗ {exc.message}")
            status.set_classes("status-line error")
            return
        # The status line below the form is the one place the result is
        # shown: a toast copy of it only covered the dialog's buttons.
        if report.get("available"):
            message = f"Connected to {report.get('source')} / {report.get('model')}"
            status.update(f"✓ {message}")
            status.set_classes("status-line success")
        else:
            reason = str(report.get("reason") or "Connection failed.")
            status.update(f"✗ {reason}")
            status.set_classes("status-line error")


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


LOGIN_HELP_TEXT = """\
[b]Signing in[/b]

  Server URL   The writing-assistant server to connect to. Start one with
               `writing-assistant`; the default is http://localhost:8001.
               Pass --server <url> or set WRITING_ASSISTANT_TUI_SERVER for a
               server on another machine or port.
  Email        Your account's email address.
  Password     Your password (at least 8 characters for a new account).

  Login              Sign in with the details above.
  Create an account  Switch to registration (adds a Confirm password field);
                     press it again ("Back to login") to switch back.

[b]Keys[/b]
  Tab / Shift+Tab   Move between the fields and buttons.
  Enter             Submit the form.
  Ctrl+C / Ctrl+V   Copy / paste in a field.
  F1                This help · Ctrl+Q or the Quit button to leave.
"""


class LoginScreen(Screen[None]):
    """Sign in or create an account on the writing-assistant server."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("f1", "help", "Help")]

    def __init__(self, session: Session, *, message: str = "") -> None:
        super().__init__()
        self._session = session
        self._message = message
        self._register_mode = False

    def compose(self) -> ComposeResult:
        with Container(id="login-wrapper"), VerticalScroll(id="login-box"):
            yield Static("TalkPipe Writing Assistant", id="login-title")
            yield Static(
                "Making the AI write [i]with[/i] you, not [i]for[/i] you.",
                id="login-tagline",
            )
            yield Label("Server URL")
            yield Input(
                value=self._session.server_url,
                placeholder="http://localhost:8001",
                id="server",
            )
            yield Label("Email")
            yield Input(
                value=self._session.email or "",
                placeholder="you@example.com",
                id="email",
            )
            yield Label("Password")
            yield Input(placeholder="password", password=True, id="password")
            yield Label("Confirm password", id="confirm-label", classes="hidden")
            yield Input(
                placeholder="repeat password",
                password=True,
                id="confirm",
                classes="hidden",
            )
            yield Static(self._message, id="login-message", classes="status-line")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Login", variant="primary", id="submit")
                yield Button("Create an account", id="toggle")
                yield Button("Quit", id="quit")
        yield Footer()

    def on_mount(self) -> None:
        target = "password" if self._session.email else "email"
        self.query_one(f"#{target}", Input).focus()
        if self._message:
            self._set_message(self._message, error=True)

    def _set_message(self, text: str, *, error: bool = False) -> None:
        widget = self.query_one("#login-message", Static)
        widget.update(text)
        widget.set_classes("status-line error" if error else "status-line")

    def action_help(self) -> None:
        self.app.push_screen(MessageScreen("Help", LOGIN_HELP_TEXT))

    @on(Button.Pressed, "#quit")
    def _quit(self) -> None:
        self.app.exit()

    @on(Button.Pressed, "#toggle")
    def _toggle(self) -> None:
        self._register_mode = not self._register_mode
        for widget_id in ("confirm-label", "confirm"):
            self.query_one(f"#{widget_id}").set_class(not self._register_mode, "hidden")
        self.query_one("#submit", Button).label = (
            "Create Account" if self._register_mode else "Login"
        )
        self.query_one("#toggle", Button).label = (
            "Back to login" if self._register_mode else "Create an account"
        )
        self.query_one("#password", Input).placeholder = (
            "password (at least 8 characters)" if self._register_mode else "password"
        )
        self._set_message("")
        # Move focus to the field the user types in next, rather than leaving
        # it on the toggled button (where a stray Enter flips the mode back and
        # typed text is dropped).
        self.query_one(
            "#confirm" if self._register_mode else "#password", Input
        ).focus()

    @on(Input.Submitted)
    @on(Button.Pressed, "#submit")
    def _submit(self) -> None:
        server = self.query_one("#server", Input).value.strip()
        email = self.query_one("#email", Input).value.strip()
        password = self.query_one("#password", Input).value
        if not server:
            self._set_message("Enter the server URL.", error=True)
            return
        if not server.startswith(("http://", "https://")):
            server = "http://" + server
        if not email or not password:
            self._set_message("Enter your email and password.", error=True)
            return
        if self._register_mode:
            confirm = self.query_one("#confirm", Input).value
            if password != confirm:
                self._set_message("Passwords do not match.", error=True)
                return
        self.query_one("#submit", Button).disabled = True
        self._set_message("Contacting server...")
        self._authenticate(server, email, password, self._register_mode)

    @work(exclusive=True)
    async def _authenticate(
        self, server: str, email: str, password: str, register: bool
    ) -> None:
        app = cast("WritingAssistantApp", self.app)
        client = app.make_client(server)
        try:
            if register:
                await client.register(email, password)
            await client.login(email, password)
        except ApiError as exc:
            await client.aclose()
            self._set_message(exc.message, error=True)
            self.query_one("#submit", Button).disabled = False
            return
        self._session.server_url = server
        self._session.email = email
        self._session.token = client.token
        self._session.save()
        app.start_editor(client, self._session)


# --------------------------------------------------------------------------
# Editor
# --------------------------------------------------------------------------


class EditorScreen(Screen[None]):
    """The main writing surface."""

    # priority=True so these win over the TextArea's own bindings (it claims
    # F6, F7 and Ctrl+U for selection/deletion), matching the web UI hotkeys.
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "file_menu", "File", priority=True),
        Binding("f3", "settings", "Settings", priority=True),
        Binding("f4", "templates", "Templates", priority=True),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+o", "open", "Open", show=False, priority=True),
        Binding("ctrl+n", "new", "New", show=False, priority=True),
        # Derived from GENERATION_MODES so adding a mode there (as the README
        # says) gives it a working key, not only a button.
        *[
            Binding(key, f"generate('{mode}')", label, show=False, priority=True)
            for mode, label, key in GENERATION_MODES
        ],
        Binding("ctrl+g", "generate('ideas')", "Ideas", show=False, priority=True),
        Binding("ctrl+u", "use_suggestion", "Use text", priority=True),
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
    ]

    def __init__(self, client: WritingAssistantClient, session: Session) -> None:
        super().__init__()
        self.client = client
        self.session = session
        self.filename: str | None = None
        self.sections: list[Section] = []
        self.current_index = -1
        self.metadata: dict[str, Any] = dict(DEFAULT_METADATA)
        self.ai: dict[str, Any] = {
            "source": "",
            "model": "",
            "server_url": "",
            "api_key": "",
            "environment_variables": {},
        }
        self.defaults: dict[str, Any] = dict(DEFAULT_METADATA)
        # The user's quick-access templates, as the server last listed them.
        self.templates: list[dict[str, Any]] = []
        self.allow_custom_env_vars = True
        self.dirty = False
        # Title/text as of the last load or save. TextArea.Changed is
        # delivered after load_text() returns, so the dirty flag is derived
        # from a comparison with this rather than from the event alone.
        self._clean_title = ""
        self._clean_text = ""
        # The generation in flight, if any, and the ones waiting behind it,
        # each as (mode, section). One request runs at a time; the rest wait
        # rather than being dropped.
        self._active: tuple[str, Section] | None = None
        self._queue: list[tuple[str, Section]] = []
        self._loading = False
        self._too_small_notified = False
        self._panel_shown: tuple[Any, ...] | None = None

    # -- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("Writing Assistant", id="brand")
            yield Static("Unsaved Document", id="filename")
            yield Static(self.session.email or "", id="user")
        with Vertical(id="workspace"):
            yield Input(placeholder="Enter document title...", id="title")
            # tab_behavior="focus": prose needs no tab characters, and Tab is
            # the only forward keyboard path to the suggestion panel/buttons.
            yield TextArea(
                id="editor",
                soft_wrap=True,
                show_line_numbers=False,
                tab_behavior="focus",
            )
            with Vertical(id="suggestion-panel"):
                with Horizontal(id="suggestion-header"):
                    yield Static(
                        "Select a section to see suggestions", id="section-info"
                    )
                    yield Static("", id="section-status")
                with VerticalScroll(id="suggestion-scroll"):
                    yield Static(
                        "Position your cursor in a section above, then choose "
                        "a mode below (or press F5-F8) to get AI suggestions "
                        "for that section.",
                        id="suggestion-text",
                        markup=False,
                    )
                with Horizontal(id="mode-bar"):
                    for mode, label, key in GENERATION_MODES:
                        yield Button(
                            f"{label} ({key.upper()})",
                            id=f"mode-{mode}",
                            classes="mode",
                        )
                    yield Button(
                        "Use This Text (Ctrl+U)",
                        variant="success",
                        id="use-suggestion",
                        disabled=True,
                    )
        yield Footer()

    async def on_mount(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.focus()
        self._fit_to_size(self.size.width, self.size.height)
        await self._load_server_state()

    def on_resize(self, event: Resize) -> None:
        self._fit_to_size(event.size.width, event.size.height)

    # Rows: topbar 1 + title 3 + editor (min 4) + panel (min 10) + footer 1 = 19,
    # so a 24-row terminal has spare rows but a 20-row one has not: below
    # COMPACT_ROWS the mode bar is dropped (the keys still work). Columns: the
    # five labelled buttons and their margins take 86 cells inside the panel,
    # which has 4 cells of border and padding, so full labels need 90 columns;
    # below that, shorter labels.
    COMPACT_ROWS: ClassVar[int] = 22
    NARROW_COLUMNS: ClassVar[int] = 90
    MIN_COLUMNS: ClassVar[int] = 60
    MIN_ROWS: ClassVar[int] = 16

    def _fit_to_size(self, width: int, height: int) -> None:
        too_small = width < self.MIN_COLUMNS or height < self.MIN_ROWS
        if too_small and not self._too_small_notified:
            self.notify(
                f"The terminal is {width}x{height}; the editor needs at least "
                f"{self.MIN_COLUMNS}x{self.MIN_ROWS}. Enlarge the window to see "
                "the suggestion panel and buttons.",
                title="Terminal too small",
                severity="warning",
                timeout=15,
            )
        self._too_small_notified = too_small
        self.set_class(height < self.COMPACT_ROWS, "compact")
        narrow = width < self.NARROW_COLUMNS
        self.set_class(narrow, "narrow")
        for mode, label, key in GENERATION_MODES:
            self.query_one(f"#mode-{mode}", Button).label = (
                label if narrow else f"{label} ({key.upper()})"
            )
        self.query_one("#use-suggestion", Button).label = (
            "Use (Ctrl+U)" if narrow else "Use This Text (Ctrl+U)"
        )

    # -- server state ----------------------------------------------------------

    async def _load_server_state(self) -> None:
        try:
            config = await self.client.server_config()
            self.allow_custom_env_vars = bool(config.get("allow_custom_env_vars", True))
        except ApiError as exc:
            self.notify(exc.message, severity="warning")
        try:
            prefs = await self.client.get_preferences()
        except AuthError:
            await self._session_expired()
            return
        except ApiError as exc:
            self.notify(
                f"Could not load preferences: {exc.message}", severity="warning"
            )
            prefs = {}
        self._apply_preferences(prefs)
        await self._fetch_templates(quiet=True)
        if self.session.last_filename:
            await self._open_document(self.session.last_filename, quiet=True)
        if not (self.metadata.get("source") or self.ai.get("source")) or not (
            self.metadata.get("model") or self.ai.get("model")
        ):
            self.notify(
                "No AI source or model is chosen yet. Press F3 → AI Settings to "
                "choose one (Test Connection tells you whether the server "
                "already provides a default).",
                title="First run",
                timeout=15,
            )

    def _apply_preferences(self, prefs: dict[str, Any]) -> None:
        for key in DEFAULT_METADATA:
            if key in prefs and prefs[key] not in (None, ""):
                self.defaults[key] = prefs[key]
        self.metadata = dict(self.defaults)
        self.ai.update(
            {
                "source": prefs.get("source") or "",
                "model": prefs.get("model") or "",
                "server_url": prefs.get("server_url") or "",
                "api_key": prefs.get("api_key") or "",
                "environment_variables": prefs.get("environment_variables") or {},
            }
        )

    async def _session_expired(self) -> None:
        cast("WritingAssistantApp", self.app).back_to_login(
            "Your session has expired. Please log in again."
        )

    async def _fetch_templates(
        self, *, quiet: bool = False
    ) -> list[dict[str, Any]] | None:
        """Refresh ``self.templates`` from the server; None when that failed.

        ``quiet`` keeps a failure (an older server without the template
        routes, say) off the screen and leaves the last list in place.
        """
        try:
            self.templates = await self.client.list_templates()
        except AuthError:
            await self._session_expired()
            return None
        except ApiError as exc:
            if not quiet:
                self.notify(exc.message, severity="error", timeout=10)
            return None
        return self.templates

    # -- helpers ---------------------------------------------------------------

    @property
    def editor(self) -> TextArea:
        return self.query_one("#editor", TextArea)

    @property
    def title_input(self) -> Input:
        return self.query_one("#title", Input)

    def _cursor_offset(self) -> int:
        # The document keeps line offsets; splitting the whole text on every
        # cursor move did work proportional to the document's length.
        editor = self.editor
        document = editor.document
        if isinstance(document, Document):
            return document.get_index_from_location(editor.cursor_location)
        row, col = editor.cursor_location  # pragma: no cover - other backends
        return sum(len(document.get_line(i)) + 1 for i in range(row)) + col

    def _location_from_offset(self, offset: int) -> tuple[int, int]:
        text = self.editor.text[:offset]
        row = text.count("\n")
        col = len(text) - (text.rfind("\n") + 1)
        return row, col

    def _set_filename(self, filename: str | None) -> None:
        self.filename = filename
        if filename != self.session.last_filename:
            self.session.last_cursor = None
        self.session.last_filename = filename
        self.session.save()
        self._refresh_header()

    def remember_cursor(self) -> None:
        """Store the cursor position so the next launch resumes there."""
        if self.filename and self.filename == self.session.last_filename:
            row, col = self.editor.cursor_location
            self.session.last_cursor = [row, col]
            self.session.save()

    def _restore_cursor(self) -> None:
        saved = self.session.last_cursor
        if not saved or len(saved) != 2:
            return
        editor = self.editor
        row = max(0, min(int(saved[0]), editor.document.line_count - 1))
        col = max(0, min(int(saved[1]), len(editor.document.get_line(row))))
        editor.move_cursor((row, col), center=True)
        self._update_current_section()

    def _refresh_header(self) -> None:
        name = self.filename or "Unsaved Document"
        marker = " ●" if self.dirty else ""
        self.query_one("#filename", Static).update(f"{name}{marker}")

    def _mark_dirty(self, dirty: bool = True) -> None:
        if not dirty:
            self._clean_title = self.title_input.value
            self._clean_text = self.editor.text
        if self.dirty != dirty:
            self.dirty = dirty
            self._refresh_header()

    def _document_payload(self) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {
            "title": self.title_input.value,
            "content": self.editor.text,
            "sections": [s.to_document_dict() for s in self.sections],
            "metadata": dict(self.metadata),
            "created_at": now,
            "updated_at": now,
        }

    def _load_document_data(self, data: dict[str, Any]) -> None:
        self._loading = True
        try:
            self.title_input.value = str(data.get("title") or "")
            self.editor.load_text(str(data.get("content") or ""))
            self.sections = parse_sections(self.editor.text)
            saved_sections = data.get("sections")
            if isinstance(saved_sections, list):
                restore_saved_sections(self.sections, saved_sections)
            metadata = data.get("metadata")
            self.metadata = dict(self.defaults)
            if isinstance(metadata, dict):
                for key in DEFAULT_METADATA:
                    if key in metadata and metadata[key] not in (None, ""):
                        self.metadata[key] = metadata[key]
        finally:
            self._loading = False
        self.editor.move_cursor((0, 0))
        self._update_current_section()
        self._mark_dirty(False)

    # -- sections and suggestions ------------------------------------------------

    @on(TextArea.Changed, "#editor")
    def _text_changed(self) -> None:
        if self._loading:
            return
        self.sections = parse_sections(self.editor.text, self.sections)
        if self.editor.text != self._clean_text:
            self._mark_dirty()
        self._update_current_section()

    @on(TextArea.SelectionChanged, "#editor")
    def _cursor_moved(self) -> None:
        if self._loading:
            return
        self._update_current_section()

    @on(Input.Changed, "#title")
    def _title_changed(self) -> None:
        if not self._loading and self.title_input.value != self._clean_title:
            self._mark_dirty()

    def _generation_state(self, section: Section) -> tuple[str, str] | None:
        """``("generating", mode)`` or ``("queued", mode)`` for ``section``."""
        if self._active is not None and self._active[1] is section:
            return "generating", self._active[0]
        for mode, queued in self._queue:
            if queued is section:
                return "queued", mode
        return None

    def _update_current_section(self) -> None:
        self.current_index = section_index_at(self.sections, self._cursor_offset())
        self._render_panel()

    def _panel_state(self) -> tuple[Any, ...]:
        """What the suggestion panel shows, for skipping redundant redraws."""
        count = len(self.sections)
        if self.current_index == -1 or count == 0:
            return (count, None)
        section = self.sections[self.current_index]
        return (
            count,
            self.current_index,
            section.generated_text,
            self._generation_state(section),
        )

    def _render_panel(self) -> None:
        # Most cursor moves stay within one section; redrawing the panel's
        # widgets (and relaying out the screen) for each of them was most of
        # the application's own per-keystroke work.
        shown = self._panel_state()
        if shown == self._panel_shown:
            return
        self._panel_shown = shown
        info = self.query_one("#section-info", Static)
        status = self.query_one("#section-status", Static)
        text = self.query_one("#suggestion-text", Static)
        use_button = self.query_one("#use-suggestion", Button)
        count = len(self.sections)
        if self.current_index == -1 or count == 0:
            info.update(
                "No sections detected — start typing"
                if count == 0
                else f"{count} section{'s' if count != 1 else ''} · place the cursor in one"
            )
            status.update("")
            text.update(
                "Position your cursor in a section above, then choose a mode "
                "below (or press F5-F8) to get AI suggestions for that section."
            )
            use_button.disabled = True
            return
        section = self.sections[self.current_index]
        info.update(f"Section {self.current_index + 1} of {count}")
        # The status belongs to the section under the cursor, not to whatever
        # request happens to be running for some other section.
        state = self._generation_state(section)
        if state is not None:
            kind, mode = state
            use_button.disabled = True
            if kind == "generating":
                status.update(f"Generating {mode}…")
                text.update("Generating AI suggestion...")
            else:
                status.update(f"Queued: {mode}")
                text.update(
                    f"Waiting for the current suggestion to finish; {mode} for "
                    "this section runs next."
                )
            return
        status.update("")
        if section.generated_text:
            text.update(section.generated_text)
            use_button.disabled = False
        else:
            text.update(
                "No suggestion yet for this section. Choose a mode below "
                "(or press F5-F8)."
            )
            use_button.disabled = True

    @on(Button.Pressed, ".mode")
    def _mode_pressed(self, event: Button.Pressed) -> None:
        mode = (event.button.id or "").removeprefix("mode-")
        self.action_generate(mode)

    def action_generate(self, mode: str) -> None:
        self._update_current_section()
        if self.current_index == -1:
            self.notify(
                "Place the cursor in a section of the document first.",
                severity="warning",
            )
            return
        section = self.sections[self.current_index]
        state = self._generation_state(section)
        if state is not None:
            self.notify(
                f"A suggestion for this section is already "
                f"{'being generated' if state[0] == 'generating' else 'queued'}.",
                severity="warning",
            )
            return
        if self._active is not None:
            # Another section's request is in flight: run this one after it
            # rather than dropping it (the previous behaviour, which looked
            # like the key had done nothing).
            self._queue.append((mode, section))
            self.notify(
                f"Queued {mode} for section {self.current_index + 1}; it runs "
                "when the current suggestion finishes."
            )
            self._update_current_section()
            return
        self._run_generation(mode, section)

    def _generation_fields(self, mode: str, index: int) -> dict[str, Any]:
        section = self.sections[index]
        prev_context, next_context = _context_around(self.sections, index)
        fields: dict[str, Any] = {
            "user_text": section.text,
            "title": self.title_input.value,
            "prev_paragraph": prev_context,
            "next_paragraph": next_context,
            "generation_mode": mode,
            "writing_style": self.metadata.get("writing_style") or "formal",
            "target_audience": self.metadata.get("target_audience") or "",
            "tone": self.metadata.get("tone") or "neutral",
            "background_context": self.metadata.get("background_context") or "",
            "generation_directive": self.metadata.get("generation_directive") or "",
            "word_limit": self.metadata.get("word_limit") or None,
            "source": self.metadata.get("source") or self.ai.get("source") or "",
            "model": self.metadata.get("model") or self.ai.get("model") or "",
        }
        if self.allow_custom_env_vars:
            fields["environment_variables"] = json.dumps(
                self.ai.get("environment_variables") or {}
            )
            fields["server_url"] = self.ai.get("server_url") or ""
            fields["api_key"] = self.ai.get("api_key") or ""
        else:
            fields["environment_variables"] = "{}"
        return fields

    @work(group="generate")
    async def _run_generation(self, mode: str, section: Section) -> None:
        text = self.query_one("#suggestion-text", Static)
        index = self._section_index(section)
        if index is None:
            # The section was removed while its request waited in the queue.
            self._start_next_generation()
            return
        self._active = (mode, section)
        self._update_current_section()
        try:
            generated = await self.client.generate_text(
                self._generation_fields(mode, index)
            )
        except AuthError:
            self._active = None
            self._queue.clear()
            await self._session_expired()
            return
        except ApiError as exc:
            # The message is shown in the suggestion panel below; a second
            # copy as a toast only stacks over the mode buttons.
            generated = ""
            error = exc.message
        else:
            error = ""
        finally:
            self._active = None
        if generated:
            # Attach to whichever current section corresponds to the one the
            # request was made for (the text may have been edited meanwhile).
            target = self._find_section(section)
            if target is not None:
                target.generated_text = generated
                target.original_text = target.text
                target.mode = mode
                self._mark_dirty()
        self._update_current_section()
        if error and self._section_index(section) == self.current_index:
            # Leave the error in the panel until the cursor moves on (or a
            # later request to the server succeeds).
            text.update(f"Error: {error}")
            self._panel_shown = None
        self._start_next_generation()

    def _start_next_generation(self) -> None:
        if self._queue:
            mode, section = self._queue.pop(0)
            self._run_generation(mode, section)

    def _section_index(self, section: Section) -> int | None:
        """Current index of ``section`` (sections are re-created on every edit)."""
        target = self._find_section(section)
        if target is None:
            return None
        return self.sections.index(target)

    def _find_section(self, original: Section) -> Section | None:
        for candidate in self.sections:
            if candidate is original:
                return candidate
        if 0 <= self.current_index < len(self.sections):
            return self.sections[self.current_index]
        return None

    @work
    async def action_use_suggestion(self) -> None:
        self._update_current_section()
        section = (
            self.sections[self.current_index] if self.current_index != -1 else None
        )
        if section is None or not section.generated_text:
            self.notify("No suggestion to use for this section.", severity="warning")
            return
        if section.mode == "ideas":
            # Ideas are advice about the section, not a rewrite of it, so
            # replacing the text with them is rarely what was meant.
            confirmed = await self.app.push_screen_wait(
                ConfirmScreen(
                    "Use ideas as text?",
                    "This suggestion is a list of ideas about the section, not "
                    "replacement text. Replace the section with it anyway? "
                    "(Ctrl+Z undoes it.)",
                    confirm_label="Replace",
                )
            )
            if not confirmed:
                return
            self._update_current_section()
            if (
                self.current_index == -1
                or self.sections[self.current_index] is not section
            ):
                return
        new_text = section.generated_text.strip()
        editor = self.editor
        start = self._location_from_offset(section.start)
        end = self._location_from_offset(section.end)
        self._loading = True
        try:
            editor.replace(new_text, start, end)
        finally:
            self._loading = False
        # Keep the suggestion attached to the replaced section.
        section.original_text = new_text
        self.sections = parse_sections(editor.text, self.sections)
        inserted = len(parse_sections(new_text))
        if inserted > 1:
            # Several sections went in: start at the first so they can be
            # read in order, rather than at the end of the last one.
            editor.move_cursor(self._location_from_offset(section.start))
        else:
            editor.move_cursor(
                self._location_from_offset(section.start + len(new_text))
            )
        self._mark_dirty()
        self._update_current_section()
        if inserted > 1:
            self.notify(
                f"Suggestion applied as {inserted} sections; the cursor is on "
                "the first."
            )
        else:
            self.notify("Suggestion applied to the section.")

    @on(Button.Pressed, "#use-suggestion")
    def _use_pressed(self) -> None:
        self.action_use_suggestion()

    # -- file actions -----------------------------------------------------------

    def action_help(self) -> None:
        self.app.push_screen(MessageScreen("Help", HELP_TEXT))

    def action_file_menu(self) -> None:
        items = [
            ("new", "New                  Ctrl+N"),
            ("save", "Save                 Ctrl+S"),
            ("save_as", "Save As"),
            ("open", "Open                 Ctrl+O"),
            ("delete", "Delete document"),
            ("snapshot", "Create snapshot"),
            ("revert", "Revert to snapshot"),
            ("import", "Import from file"),
            ("export", "Export to file"),
            ("copy", "Copy document to clipboard"),
            ("account", "Account (email, password)"),
            ("logout", "Log out"),
        ]
        self.app.push_screen(MenuScreen("File", items), self._file_menu_chosen)

    def _file_menu_chosen(self, choice: str | None) -> None:
        if choice is None:
            return
        handler = {
            "new": self.action_new,
            "save": self.action_save,
            "save_as": self.action_save_as,
            "open": self.action_open,
            "delete": self.action_delete,
            "snapshot": self.action_snapshot,
            "revert": self.action_revert,
            "import": self.action_import,
            "export": self.action_export,
            "copy": self.action_copy,
            "account": self.action_account,
            "logout": self.action_logout,
        }[choice]
        handler()

    async def _confirm_discard(self, what: str) -> bool:
        """Ask what to do about unsaved changes; True means go ahead.

        "Save" saves first (asking for a name if the document has none) and
        goes ahead only when that succeeded.
        """
        if not self.dirty:
            return True
        choice = await self.app.push_screen_wait(UnsavedChangesScreen(what))
        if choice == "save":
            return await self._save_now()
        return choice == "discard"

    async def _save_now(self) -> bool:
        if self.filename:
            return await self._save_document(self.filename, save_as=False)
        return await self._ask_save_as()

    @work
    async def action_new(self) -> None:
        if not await self._confirm_discard("Start a new document"):
            return
        result = await self.app.push_screen_wait(NewDocumentScreen())
        if result is None:
            return
        title, outline = result
        self._set_filename(None)
        self._load_document_data(
            {"title": title, "content": outline, "metadata": dict(self.defaults)}
        )
        self._mark_dirty(bool(title or outline))
        self.editor.focus()
        self.notify("New document started — Ctrl+S stores it in your library.")

    @work
    async def action_templates(self) -> None:
        """F4: start a new document from a quick-access template."""
        while True:
            templates = await self._fetch_templates()
            if templates is None:
                return
            if not templates:
                self.notify(
                    "No templates yet. Press F3, fill in the writing settings, "
                    "and press Save as Template on the Document tab.",
                    title="Templates",
                    timeout=10,
                )
                return
            entries = [
                (
                    str(t["id"]),
                    f"{t['name']}  —  {template_summary(t.get('settings') or {})}",
                )
                for t in templates
            ]
            result = await self.app.push_screen_wait(
                PickerScreen(
                    "New Document from Template",
                    entries,
                    open_label="New document",
                    extra_buttons=[("delete", "Delete")],
                )
            )
            if result is None:
                return
            action, template_id = result
            template = next(
                (t for t in templates if str(t.get("id")) == template_id), None
            )
            if template is None:
                continue
            if action == "delete":
                await self._delete_template(template)
                continue
            await self._new_from_template(template)
            return

    async def _delete_template(self, template: dict[str, Any]) -> None:
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(
                "Delete template",
                f'Delete the template "{template["name"]}"? Documents that used '
                "it keep their settings.",
                confirm_label="Delete",
            )
        )
        if not confirmed:
            return
        try:
            message = await self.client.delete_template(int(template["id"]))
        except AuthError:
            await self._session_expired()
            return
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        self.notify(message)

    async def _new_from_template(self, template: dict[str, Any]) -> None:
        """Replace the editor with an empty document using the template's settings.

        The document being left is saved rather than discarded when it has
        a library name; one that was never saved gets the usual Save /
        Discard / Cancel prompt, since there is no name to save it under.
        """
        saved_note = ""
        if self.dirty and self.filename:
            if not await self._save_document(self.filename, save_as=False):
                return
            saved_note = f' "{self.filename}" was saved first.'
        elif not await self._confirm_discard("Start a new document from the template"):
            return
        self._set_filename(None)
        # Blank template fields fall back to the user's defaults, as blank
        # document fields do (and as the web UI's form does).
        self._load_document_data(
            {"title": "", "content": "", "metadata": template.get("settings") or {}}
        )
        self._mark_dirty(False)
        self.editor.focus()
        self.notify(
            f'New document from template "{template["name"]}".{saved_note} '
            "Ctrl+S stores it in your library."
        )

    def action_save(self) -> None:
        if self.filename:
            self._save_as(self.filename, save_as=False)
        else:
            self.action_save_as()

    @work
    async def action_save_as(self) -> None:
        await self._ask_save_as()

    async def _ask_save_as(self) -> bool:
        suggested = self.filename or _suggest_filename(self.title_input.value)
        filename = await self.app.push_screen_wait(
            PromptScreen(
                "Save As",
                "Name in your library (kept on the server, shared with the web "
                "UI — not a file on this machine; use File → Export for that). "
                "Library names end in .json, as the web UI shows them.",
                default=suggested,
                placeholder="my-document.json",
                confirm_label="Save",
            )
        )
        if not filename:
            return False
        if not filename.endswith(".json"):
            filename += ".json"
        if filename != self.filename and not await self._confirm_overwrite(filename):
            return False
        return await self._save_document(filename, save_as=True)

    async def _confirm_overwrite(self, filename: str) -> bool:
        """Ask before Save As replaces a different document in the library."""
        try:
            documents = await self.client.list_documents()
        except AuthError:
            await self._session_expired()
            return False
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return False
        if not any(doc.get("filename") == filename for doc in documents):
            return True
        result = await self.app.push_screen_wait(
            ConfirmScreen(
                "Overwrite document",
                f'"{filename}" already exists. Replace it with this document?',
                confirm_label="Overwrite",
            )
        )
        return bool(result)

    @work
    async def _save_as(self, filename: str, *, save_as: bool) -> None:
        await self._save_document(filename, save_as=save_as)

    async def _save_document(self, filename: str, *, save_as: bool) -> bool:
        try:
            message = await self.client.save_document(
                filename, self._document_payload(), save_as=save_as
            )
        except AuthError:
            await self._session_expired()
            return False
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return False
        self._set_filename(filename)
        self._mark_dirty(False)
        self.remember_cursor()
        # A "could not connect" error left in the panel is stale now.
        self._update_current_section()
        self.notify(f"{message}: {filename}")
        return True

    @work
    async def action_open(self) -> None:
        if not await self._confirm_discard("Open another document"):
            return
        while True:
            try:
                documents = await self.client.list_documents()
            except AuthError:
                await self._session_expired()
                return
            except ApiError as exc:
                self.notify(exc.message, severity="error", timeout=10)
                return
            entries = [
                (
                    str(doc.get("filename")),
                    (
                        f"{doc.get('filename')}  —  {doc.get('title') or '(untitled)'}"
                        f"  ·  {_format_timestamp(doc.get('modified'))}"
                    ),
                )
                for doc in documents
            ]
            result = await self.app.push_screen_wait(
                PickerScreen(
                    "Open Document",
                    entries,
                    empty_message="No saved documents yet. Use File → Save to create one.",
                    extra_buttons=[("delete", "Delete"), ("refresh", "Refresh")],
                )
            )
            if result is None:
                return
            action, filename = result
            if action == "refresh":
                continue
            if action == "delete":
                if await self._delete_document(filename):
                    continue
                return
            await self._open_document(filename)
            return

    async def _open_document(self, filename: str, *, quiet: bool = False) -> None:
        try:
            data = await self.client.load_document(filename)
        except AuthError:
            await self._session_expired()
            return
        except ApiError as exc:
            if quiet:
                self.session.last_filename = None
                self.session.save()
            else:
                self.notify(exc.message, severity="error", timeout=10)
            return
        self._set_filename(filename)
        self._load_document_data(data)
        if quiet:
            # Reopened on launch: pick up where the last session left off.
            self._restore_cursor()
        self.editor.focus()
        if not quiet:
            self.notify(f'Opened "{filename}".')

    async def _delete_document(self, filename: str) -> bool:
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(
                "Delete document",
                f'Delete "{filename}" and all of its snapshots? This cannot be undone.',
                confirm_label="Delete",
            )
        )
        if not confirmed:
            return False
        try:
            message = await self.client.delete_document(filename)
        except AuthError:
            await self._session_expired()
            return False
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return False
        if self.filename == filename:
            self._set_filename(None)
            self._mark_dirty(True)
            # The text is deliberately left in the editor as a way back;
            # say so, or it looks as if the delete failed.
            self.notify(
                f"{message}. Its text stays in the editor: Save As keeps it, "
                "Ctrl+N starts fresh.",
                timeout=10,
            )
        else:
            self.notify(message)
        return True

    @work
    async def action_delete(self) -> None:
        if not self.filename:
            self.notify("This document has not been saved yet.", severity="warning")
            return
        await self._delete_document(self.filename)

    @work
    async def action_snapshot(self) -> None:
        if not self.filename:
            self.notify(
                "Save the document before creating a snapshot.", severity="warning"
            )
            return
        if self.dirty:
            confirmed = await self.app.push_screen_wait(
                ConfirmScreen(
                    "Unsaved changes",
                    "Snapshots capture the last saved version. Save first?",
                    confirm_label="Save and snapshot",
                )
            )
            if not confirmed:
                return
            try:
                await self.client.save_document(self.filename, self._document_payload())
            except ApiError as exc:
                self.notify(exc.message, severity="error", timeout=10)
                return
            self._mark_dirty(False)
        try:
            message = await self.client.create_snapshot(self.filename)
        except AuthError:
            await self._session_expired()
            return
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        self.notify(message)

    @work
    async def action_revert(self) -> None:
        if not self.filename:
            self.notify(
                "Open a saved document to see its snapshots.", severity="warning"
            )
            return
        try:
            snapshots = await self.client.list_snapshots(self.filename)
        except AuthError:
            await self._session_expired()
            return
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        entries = [
            (
                str(snap.get("filename")),
                f"{_format_timestamp(snap.get('modified'))}  ·  {snap.get('filename')}",
            )
            for snap in snapshots
        ]
        result = await self.app.push_screen_wait(
            PickerScreen(
                "Revert to Snapshot",
                entries,
                empty_message="No snapshots for this document yet. Use File → Create snapshot.",
                open_label="Revert",
            )
        )
        if result is None:
            return
        _, snapshot_name = result
        if not await self._confirm_discard("Revert to this snapshot"):
            return
        try:
            data = await self.client.load_snapshot(snapshot_name)
        except ApiError as exc:
            self.notify(exc.message, severity="error", timeout=10)
            return
        self._load_document_data(data)
        self._mark_dirty(True)
        self.notify("Snapshot loaded into the editor — save to keep it.")

    @work
    async def action_import(self) -> None:
        if not await self._confirm_discard("Import a file"):
            return
        path_text = await self.app.push_screen_wait(
            PromptScreen(
                "Import",
                "Path to a document JSON file (exported from the writing assistant)",
                placeholder="~/Documents/my-document.json",
                confirm_label="Import",
            )
        )
        if not path_text:
            return
        path = Path(path_text).expanduser()
        try:
            data = json.loads(path.read_text())
        except OSError as exc:
            self.notify(f"Could not read {path}: {exc.strerror}", severity="error")
            return
        except ValueError:
            self.notify(f"{path} is not valid JSON.", severity="error")
            return
        if not isinstance(data, dict):
            self.notify(
                "That file is not a writing-assistant document.", severity="error"
            )
            return
        self._set_filename(None)
        self._load_document_data(data)
        self._mark_dirty(True)
        self.notify(f'Imported "{path.name}" — use Save to store it on the server.')

    @work
    async def action_export(self) -> None:
        default_name = self.filename or _suggest_filename(self.title_input.value)
        path_text = await self.app.push_screen_wait(
            PromptScreen(
                "Export",
                "Write the document JSON to",
                default=str(Path.cwd() / default_name),
                confirm_label="Export",
            )
        )
        if not path_text:
            return
        path = Path(path_text).expanduser()
        if path.exists():
            confirmed = await self.app.push_screen_wait(
                ConfirmScreen(
                    "Overwrite file",
                    f"{path} already exists. Overwrite it?",
                    confirm_label="Overwrite",
                )
            )
            if not confirmed:
                return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._document_payload(), indent=2))
        except OSError as exc:
            self.notify(f"Could not write {path}: {exc.strerror}", severity="error")
            return
        self.notify(f"Exported to {path}")

    def action_copy(self) -> None:
        title = self.title_input.value.strip()
        body = self.editor.text
        text = f"{title}\n\n{body}" if title else body
        self.app.copy_to_clipboard(text)
        if system_clipboard_available():
            self.notify("Document copied to the clipboard.")
        else:
            # e.g. over SSH: no wl-copy/xclip/xsel/pbcopy, so the copy only
            # reached the app's own clipboard and the terminal's OSC 52 (which
            # not every terminal honours). Say so rather than imply success.
            self.notify(
                "Document copied. No clipboard tool (wl-copy/xclip/xsel/"
                "pbcopy) was found, so if pasting elsewhere fails, use "
                "File → Export to write it to a file.",
                severity="warning",
                timeout=10,
            )

    @work
    async def action_account(self) -> None:
        # The document is untouched, so no unsaved-changes prompt; the
        # session token stays valid, so no re-login either.
        self.app.clear_notifications()
        changed = await self.app.push_screen_wait(
            AccountScreen(self.client, self.session)
        )
        # The dialog saved the session; the top bar is ours to refresh.
        self.query_one("#user", Static).update(self.session.email or "")
        if "email" in changed:
            self.notify(f"Email changed to {self.session.email}.")
        if "password" in changed:
            self.notify("Password changed.")

    @work
    async def action_logout(self) -> None:
        if not await self._confirm_discard("Log out"):
            return
        await self.client.logout()
        self.session.token = None
        self.session.save()
        cast("WritingAssistantApp", self.app).back_to_login("")

    @work
    async def action_quit_app(self) -> None:
        if not await self._confirm_discard("Quit"):
            return
        self.remember_cursor()
        self.app.exit()

    # -- settings ---------------------------------------------------------------

    @work
    async def action_settings(self) -> None:
        # A lingering toast (the first-run hint, say) would sit over the
        # dialog's buttons.
        self.app.clear_notifications()
        metadata = dict(self.metadata)
        # Templates may have been added from the web UI meanwhile; a failure
        # here (an older server) just leaves the last list in place.
        await self._fetch_templates(quiet=True)
        result = await self.app.push_screen_wait(
            SettingsScreen(
                metadata,
                self.ai,
                allow_custom_env_vars=self.allow_custom_env_vars,
                editor=self,
                templates=self.templates,
            )
        )
        if result is None:
            return
        action = result["action"]
        new_metadata: dict[str, Any] = result["metadata"]
        new_ai: dict[str, Any] = result["ai"]
        if action in ("document", "default"):
            self.metadata = new_metadata
            self._mark_dirty()
            if action == "document":
                self.notify("Settings saved to this document.")
        if action in ("default", "ai"):
            self.ai = new_ai
            preferences = {
                **{k: new_metadata[k] for k in DEFAULT_METADATA},
                **new_ai,
            }
            try:
                await self.client.save_preferences(preferences)
            except AuthError:
                await self._session_expired()
                return
            except ApiError as exc:
                self.notify(exc.message, severity="error", timeout=10)
                return
            if action == "default":
                self.defaults = {k: new_metadata[k] for k in DEFAULT_METADATA}
                self.notify(
                    "Saved as your default settings and applied to this document."
                )
            else:
                self.defaults["source"] = new_ai["source"]
                self.defaults["model"] = new_ai["model"]
                # The open document uses the new source/model from now on,
                # as in the web client; it is saved with the next Save.
                if (
                    self.metadata.get("source") != new_ai["source"]
                    or self.metadata.get("model") != new_ai["model"]
                ):
                    self.metadata["source"] = new_ai["source"]
                    self.metadata["model"] = new_ai["model"]
                    # An empty, never-saved document has nothing to lose, so
                    # do not turn it into "unsaved changes" on quit.
                    if self.filename or self.title_input.value or self.editor.text:
                        self._mark_dirty()
                self.notify("AI settings saved.")


def _context_around(sections: list[Section], index: int) -> tuple[str, str]:
    from .sections import SectionState

    return SectionState(sections, index).context_around(index)


def _suggest_filename(title: str) -> str:
    slug = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in title.strip().lower()
    )
    slug = "-".join(part for part in slug.split("-") if part)
    return f"{slug or 'document'}.json"


def _format_timestamp(value: Any) -> str:
    """Render a server timestamp in local time.

    Current servers send an explicit ``+00:00`` offset. Servers from before
    that sent bare UTC, so a value with no offset is still treated as UTC.
    """
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone().strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------


class EditorCommands(Provider):
    """Command-palette (Ctrl+P) entries for the editor's actions.

    Mirrors the File menu, Settings, Help and the generation modes so the
    palette advertised in the footer can find the application's own
    commands, not just Textual's built-ins.
    """

    def _commands(self) -> list[tuple[str, str, Callable[[], Any]]]:
        screen = self.screen
        if not isinstance(screen, EditorScreen):
            return []
        commands: list[tuple[str, str, Callable[[], Any]]] = [
            (f"{label}: {help_text}", "", getattr(screen, f"action_{name}"))
            for name, label, help_text in EDITOR_COMMANDS
        ]
        commands.extend(
            (
                f"{label} the current section",
                f"AI suggestion ({key.upper()})",
                partial(screen.action_generate, mode),
            )
            for mode, label, key in GENERATION_MODES
        )
        return commands

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for title, help_text, callback in self._commands():
            score = matcher.match(title)
            if score > 0:
                yield Hit(
                    score, matcher.highlight(title), callback, help=help_text or None
                )

    async def discover(self) -> Hits:
        for title, help_text, callback in self._commands():
            yield DiscoveryHit(title, callback, help=help_text or None)


EDITOR_COMMANDS: list[tuple[str, str, str]] = [
    ("new", "New document", "Start a new document (Ctrl+N)"),
    ("save", "Save", "Save the document (Ctrl+S)"),
    ("save_as", "Save As", "Save the document under another name"),
    ("open", "Open", "Open a document from the library (Ctrl+O)"),
    ("delete", "Delete document", "Delete the open document from the library"),
    ("snapshot", "Create snapshot", "Keep a copy of the saved document"),
    ("revert", "Revert to snapshot", "Load an earlier snapshot into the editor"),
    ("import", "Import from file", "Load a document JSON file"),
    ("export", "Export to file", "Write the document JSON to a file"),
    ("copy", "Copy document to clipboard", "Copy the document text"),
    ("settings", "Settings", "Document and AI settings (F3)"),
    ("templates", "New from template", "Start a document from a template (F4)"),
    ("help", "Help", "Keyboard reference (F1)"),
    ("use_suggestion", "Use suggestion", "Replace the section with it (Ctrl+U)"),
    ("account", "Account", "Change your email address or password"),
    ("logout", "Log out", "Forget the saved session and return to login"),
]


class WritingAssistantApp(App[None]):
    """Textual application: login screen first, then the editor."""

    TITLE = "Writing Assistant"
    CSS_PATH = "app.tcss"
    COMMANDS: ClassVar[set[type[Provider] | Callable[[], type[Provider]]]] = {
        *App.COMMANDS,
        EditorCommands,
    }
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(
        self,
        session: Session | None = None,
        *,
        client_factory: Any = None,
    ) -> None:
        super().__init__()
        self.session = session or Session.load()
        self._client_factory = client_factory
        self._client: WritingAssistantClient | None = None

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        # Only the built-ins that mean something here: Textual's Theme,
        # Maximize and Screenshot entries are not part of the documented
        # interface and confused a first-time user of the palette.
        for command in super().get_system_commands(screen):
            if command.title in ("Quit", "Keys"):
                yield command

    # Textual's Ctrl+V pastes from a clipboard internal to the app, so text
    # copied in another program never arrived (the terminal's own paste,
    # Ctrl+Shift+V, does work — it comes in as a bracketed paste, not a key).
    # Prefer the system clipboard when a clipboard tool is available, and
    # mirror in-app copies to it so the two never disagree.
    @property
    def clipboard(self) -> str:
        system = read_system_clipboard()
        if system:
            return system
        return self._clipboard

    def copy_to_clipboard(self, text: str) -> None:
        super().copy_to_clipboard(text)
        write_system_clipboard(text)

    def make_client(self, server_url: str, token: str | None = None) -> Any:
        if self._client_factory is not None:
            return self._client_factory(server_url, token)
        return WritingAssistantClient(server_url, token)

    async def on_mount(self) -> None:
        if self.session.token:
            client = self.make_client(self.session.server_url, self.session.token)
            try:
                await client.check_auth()
            except ApiError as exc:
                await client.aclose()
                self.session.token = None
                message = (
                    exc.message
                    if not isinstance(exc, AuthError)
                    else "Your saved session has expired. Please log in again."
                )
                await self.push_screen(LoginScreen(self.session, message=message))
                return
            self._client = client
            await self.push_screen(EditorScreen(client, self.session))
            return
        await self.push_screen(LoginScreen(self.session))

    def start_editor(self, client: Any, session: Session) -> None:
        """Replace the current screen with the editor.

        Not awaited: callers run inside a worker owned by the screen being
        replaced, and awaiting the switch from there would wait on itself.
        """
        old_client = self._client if self._client is not client else None
        self._client = client
        self.call_later(self._switch_to, EditorScreen(client, session), old_client)

    def back_to_login(self, message: str) -> None:
        """Replace the current screen with the login screen (see start_editor)."""
        old_client, self._client = self._client, None
        self.call_later(
            self._switch_to, LoginScreen(self.session, message=message), old_client
        )

    async def _switch_to(self, screen: Screen[None], old_client: Any) -> None:
        await self.switch_screen(screen)
        if old_client is not None:
            await old_client.aclose()

    async def action_quit(self) -> None:
        screen = self.screen
        if isinstance(screen, EditorScreen):
            screen.action_quit_app()
            return
        self.exit()

    async def on_unmount(self) -> None:
        if self._client is not None:
            await self._client.aclose()


def main(argv: list[str] | None = None) -> None:
    """Console entry point: ``writing-assistant-tui``."""
    parser = argparse.ArgumentParser(
        prog="writing-assistant-tui",
        description=(
            "Terminal interface for the TalkPipe Writing Assistant. Connects to "
            "a running writing-assistant server (start one with "
            "`writing-assistant`) and offers the same features as the web UI."
        ),
        epilog=(
            "The login token and the last-open document are remembered in "
            "~/.writing_assistant/tui_session.json (mode 600); set "
            "WRITING_ASSISTANT_TUI_HOME to keep that file elsewhere. Press F1 "
            "inside the application for the keyboard reference."
        ),
    )
    parser.add_argument(
        "--server",
        default=None,
        help=(
            "Server URL (default: WRITING_ASSISTANT_TUI_SERVER if set, else the "
            "last one used, else http://localhost:8001)"
        ),
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Forget the saved session token and show the login screen",
    )
    args = parser.parse_args(argv)

    session = Session.load()
    server = args.server or os.getenv("WRITING_ASSISTANT_TUI_SERVER")
    if server:
        server = server.rstrip("/")
        if server != session.server_url:
            session.token = None
        session.server_url = server
    if args.logout:
        session.token = None
        session.save()

    WritingAssistantApp(session).run()


if __name__ == "__main__":  # pragma: no cover
    main()
