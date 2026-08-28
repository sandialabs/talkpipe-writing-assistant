"""Read and write the system clipboard from the terminal interface.

Textual's Ctrl+V pastes from a clipboard that is internal to the app (filled
by Ctrl+C in the editor), and writes copies out with an OSC 52 escape that
not every terminal honours. Neither reaches text copied in another program.
This module bridges to the desktop clipboard through whichever command-line
tool is installed — ``wl-paste``/``wl-copy`` (Wayland), ``xclip`` or
``xsel`` (X11), ``pbpaste``/``pbcopy`` (macOS) — and degrades to "no system
clipboard" when none is present, e.g. over SSH; the terminal's own paste
(Ctrl+Shift+V, Shift+Insert) keeps working regardless because it arrives as
a bracketed-paste sequence, not as a key.
"""

from __future__ import annotations

import shutil

# Bandit B404: the only executables run are the fixed clipboard tools listed in
# _TOOLS/_WRITERS, resolved to absolute paths, with shell=False; clipboard text
# reaches them via stdin, never the command line.
import subprocess  # nosec B404

_TIMEOUT = 2.0

# (executable, read arguments, write arguments), in order of preference.
_TOOLS: tuple[tuple[str, list[str], list[str]], ...] = (
    ("wl-paste", ["--no-newline"], []),  # wl-copy is the writer, see below
    ("xclip", ["-selection", "clipboard", "-o"], ["-selection", "clipboard"]),
    ("xsel", ["--clipboard", "--output"], ["--clipboard", "--input"]),
    ("pbpaste", [], []),
)
_WRITERS: dict[str, str] = {"wl-paste": "wl-copy", "pbpaste": "pbcopy"}


def _find_tool() -> tuple[str, list[str], str, list[str]] | None:
    """Return (reader, read args, writer, write args) for the first tool found.

    The reader and writer are the absolute paths ``shutil.which`` resolved, so
    the process is started from that path rather than by a second PATH lookup.
    """
    for name, read_args, write_args in _TOOLS:
        reader = shutil.which(name)
        if reader is None:
            continue
        writer = shutil.which(_WRITERS.get(name, name))
        if writer is None:
            continue
        return reader, read_args, writer, write_args
    return None


def system_clipboard_available() -> bool:
    """True when a clipboard tool (wl-copy/xclip/xsel/pbcopy) is installed."""
    return _find_tool() is not None


def read_system_clipboard() -> str | None:
    """Return the system clipboard text, or None when it cannot be read."""
    tool = _find_tool()
    if tool is None:
        return None
    reader, read_args, _, _ = tool
    try:
        # B603: argv is a resolved tool path plus fixed flags from _TOOLS.
        result = subprocess.run(  # nosec B603
            [reader, *read_args],
            capture_output=True,
            timeout=_TIMEOUT,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def write_system_clipboard(text: str) -> bool:
    """Copy ``text`` to the system clipboard; return whether it succeeded."""
    tool = _find_tool()
    if tool is None:
        return False
    _, _, writer, write_args = tool
    try:
        # B603: argv is a resolved tool path plus fixed flags; text goes via stdin.
        result = subprocess.run(  # nosec B603
            [writer, *write_args],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=_TIMEOUT,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0
