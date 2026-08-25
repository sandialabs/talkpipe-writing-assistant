"""Persisted TUI session file."""

import json
import os
import stat

from writing_assistant.tui.session import Session, session_path


def test_session_path_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WRITING_ASSISTANT_TUI_HOME", str(tmp_path))
    assert session_path() == tmp_path / "tui_session.json"


def test_session_round_trip_and_permissions(monkeypatch, tmp_path):
    monkeypatch.setenv("WRITING_ASSISTANT_TUI_HOME", str(tmp_path / "nested"))
    session = Session(
        server_url="http://h:1",
        token="t",
        email="e@x",
        last_filename="a.json",
        last_cursor=[3, 7],
    )
    session.save()
    assert Session.load() == session
    mode = stat.S_IMODE(os.stat(session_path()).st_mode)
    assert mode == 0o600


def test_session_load_tolerates_bad_files(monkeypatch, tmp_path):
    monkeypatch.setenv("WRITING_ASSISTANT_TUI_HOME", str(tmp_path))
    assert Session.load() == Session()  # missing
    session_path().write_text("not json")
    assert Session.load() == Session()
    session_path().write_text(json.dumps([1, 2]))
    assert Session.load() == Session()
    session_path().write_text(json.dumps({"token": "t", "unknown": 1}))
    assert Session.load().token == "t"
    # Files written before the cursor was remembered still load.
    session_path().write_text(json.dumps({"last_filename": "a.json"}))
    assert Session.load().last_cursor is None
