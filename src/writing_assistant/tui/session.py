"""Persisted TUI session: server URL, bearer token, last-open document.

The web UI keeps these in the browser's localStorage; the TUI keeps the
equivalent in ``~/.writing_assistant/tui_session.json`` (override the
directory with ``WRITING_ASSISTANT_TUI_HOME``) so a reopened terminal picks
up where it left off without logging in again while the token is valid.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SESSION_FILENAME = "tui_session.json"


def session_path() -> Path:
    home = os.getenv("WRITING_ASSISTANT_TUI_HOME")
    base = Path(home).expanduser() if home else Path.home() / ".writing_assistant"
    return base / SESSION_FILENAME


@dataclass
class Session:
    server_url: str = "http://localhost:8001"
    token: str | None = None
    email: str | None = None
    last_filename: str | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> Session:
        path = path or session_path()
        try:
            raw = json.loads(path.read_text())
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = set(cls.__dataclass_fields__)
        data = {k: v for k, v in raw.items() if k in known}
        return cls(**data)

    def save(self, path: Path | None = None) -> None:
        path = path or session_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))
        # The file holds a bearer token: keep it private to the user.
        with contextlib.suppress(OSError):
            path.chmod(0o600)
