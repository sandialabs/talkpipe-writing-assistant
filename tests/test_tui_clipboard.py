"""Unit tests for the system-clipboard bridge (no clipboard tool is run)."""

import subprocess

from writing_assistant.tui import clipboard


def test_read_returns_none_without_a_tool(mocker):
    mocker.patch("writing_assistant.tui.clipboard.shutil.which", return_value=None)
    run = mocker.patch("writing_assistant.tui.clipboard.subprocess.run")
    assert clipboard.read_system_clipboard() is None
    assert clipboard.write_system_clipboard("x") is False
    run.assert_not_called()


def test_read_and_write_use_the_first_available_tool(mocker):
    def which(name):
        return f"/usr/bin/{name}" if name in {"xclip"} else None

    mocker.patch("writing_assistant.tui.clipboard.shutil.which", side_effect=which)
    run = mocker.patch(
        "writing_assistant.tui.clipboard.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout=b"hello\nworld"),
    )
    assert clipboard.read_system_clipboard() == "hello\nworld"
    # The resolved absolute path is run, not a bare name looked up on PATH again.
    assert run.call_args.args[0] == ["/usr/bin/xclip", "-selection", "clipboard", "-o"]
    assert run.call_args.kwargs["shell"] is False
    assert clipboard.write_system_clipboard("hi") is True
    assert run.call_args.args[0] == ["/usr/bin/xclip", "-selection", "clipboard"]
    assert run.call_args.kwargs["input"] == b"hi"
    assert run.call_args.kwargs["shell"] is False


def test_wayland_writer_is_the_resolved_wl_copy_path(mocker):
    def which(name):
        return f"/opt/wl/{name}" if name in {"wl-paste", "wl-copy"} else None

    mocker.patch("writing_assistant.tui.clipboard.shutil.which", side_effect=which)
    run = mocker.patch(
        "writing_assistant.tui.clipboard.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout=b"x"),
    )
    assert clipboard.read_system_clipboard() == "x"
    assert run.call_args.args[0] == ["/opt/wl/wl-paste", "--no-newline"]
    assert clipboard.write_system_clipboard("y") is True
    assert run.call_args.args[0] == ["/opt/wl/wl-copy"]


def test_wayland_reader_requires_its_writer(mocker):
    # wl-paste present but wl-copy missing: fall through to xsel.
    def which(name):
        return f"/usr/bin/{name}" if name in {"wl-paste", "xsel"} else None

    mocker.patch("writing_assistant.tui.clipboard.shutil.which", side_effect=which)
    run = mocker.patch(
        "writing_assistant.tui.clipboard.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout=b"x"),
    )
    assert clipboard.read_system_clipboard() == "x"
    assert run.call_args.args[0][0] == "/usr/bin/xsel"


def test_failures_degrade_to_none_and_false(mocker):
    mocker.patch(
        "writing_assistant.tui.clipboard.shutil.which", return_value="/usr/bin/xsel"
    )
    mocker.patch(
        "writing_assistant.tui.clipboard.subprocess.run",
        side_effect=subprocess.TimeoutExpired("xsel", 2),
    )
    assert clipboard.read_system_clipboard() is None
    assert clipboard.write_system_clipboard("x") is False
    mocker.patch(
        "writing_assistant.tui.clipboard.subprocess.run",
        return_value=subprocess.CompletedProcess([], 1, stdout=b""),
    )
    assert clipboard.read_system_clipboard() is None
    assert clipboard.write_system_clipboard("x") is False
