"""Tests for the server.py module."""

import http.server
import json
import os
import socket
import threading
import time
from unittest.mock import patch

import pytest

from writing_assistant.app import auth, server

_REAL_PORT_IN_USE = server.port_in_use
_REAL_LAUNCH_BROWSER = server._launch_browser_when_ready
_REAL_RUNNING_INSTANCE_URL = server._running_instance_url


@pytest.fixture(autouse=True)
def browser_launches(monkeypatch):
    """Keep main() deterministic and away from the developer's desktop.

    Without this, every test that patches uvicorn.run would still probe
    localhost:8001 (a writing assistant really running there would change
    the chosen port or short-circuit as "already running") and would spawn
    the browser-opening thread. Tests that need the real port probe restore
    it with ``_REAL_PORT_IN_USE``.
    """
    launches: list[tuple[str, int]] = []
    monkeypatch.setattr(server, "_running_instance_url", lambda host, port: None)
    monkeypatch.setattr(server, "port_in_use", lambda host, port: False)
    monkeypatch.setattr(
        server,
        "_launch_browser_when_ready",
        lambda host, port, timeout=15.0: launches.append((host, port)),
    )
    return launches


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_default_arguments(mock_port_check, mock_uvicorn_run):
    """Test main function with default arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with default values
    mock_uvicorn_run.assert_called_once()
    _args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 8001
    assert not kwargs["reload"]


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0", "--port", "9000", "--reload"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_custom_arguments(mock_port_check, mock_uvicorn_run):
    """Test main function with custom arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with custom values
    mock_uvicorn_run.assert_called_once()
    _args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 9000
    assert kwargs["reload"]


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--disable-custom-env-vars"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_disable_custom_env_vars(mock_port_check, mock_uvicorn_run, monkeypatch):
    """Test main function with custom env vars disabled."""
    import writing_assistant.app.main as main_module
    from writing_assistant.app.server import main

    # main() flips the module-level flag; restore it so later tests (the TUI
    # settings dialog, for one) see the default.
    monkeypatch.setattr(main_module, "ALLOW_CUSTOM_ENV_VARS", True)
    main()

    assert main_module.ALLOW_CUSTOM_ENV_VARS is False
    # Verify uvicorn.run was called
    mock_uvicorn_run.assert_called_once()


@patch.dict(
    os.environ,
    {
        "WRITING_ASSISTANT_HOST": "192.168.1.100",
        "WRITING_ASSISTANT_PORT": "8080",
        "WRITING_ASSISTANT_RELOAD": "true",
    },
)
@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_environment_variables(mock_port_check, mock_uvicorn_run):
    """Test main function with environment variables."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with environment variable values
    mock_uvicorn_run.assert_called_once()
    _args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "192.168.1.100"
    assert kwargs["port"] == 8080
    assert kwargs["reload"]


@patch.dict(os.environ, {"WRITING_ASSISTANT_RELOAD": "false"})
@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_reload_false_environment(mock_port_check, mock_uvicorn_run):
    """Test main function with reload disabled via environment variable."""
    from writing_assistant.app.server import main

    main()

    # Verify reload is false
    mock_uvicorn_run.assert_called_once()
    _args, kwargs = mock_uvicorn_run.call_args
    assert not kwargs["reload"]


@patch.dict(os.environ, {"WRITING_ASSISTANT_RELOAD": "TRUE"})
@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_reload_true_case_insensitive(mock_port_check, mock_uvicorn_run):
    """Test main function with reload enabled (case insensitive)."""
    from writing_assistant.app.server import main

    main()

    # Verify reload is true (case insensitive)
    mock_uvicorn_run.assert_called_once()
    _args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["reload"]


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("builtins.print")
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_prints_server_info(mock_port_check, mock_print, mock_uvicorn_run):
    """Test that main function prints server information."""
    from writing_assistant.app.server import main

    main()

    # Verify print statements were called
    assert mock_print.call_count >= 4

    # Check that key information is printed
    print_calls = [call[0][0] for call in mock_print.call_args_list]

    # Should print server header
    assert any("Writing Assistant Server" in call for call in print_calls)
    # Should print access URL
    assert any("Access your writing assistant at:" in call for call in print_calls)
    # Should print registration URL
    assert any("Register a new account at:" in call for call in print_calls)


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0", "--disable-custom-env-vars"])
@patch("builtins.print")
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_banner_for_wildcard_bind(
    mock_port_check, mock_print, mock_uvicorn_run, monkeypatch
):
    """`http://0.0.0.0:8001/` is not a URL anyone can open: the banner names
    the machine instead, says it listens on all interfaces, and notes that
    custom environment variables are off."""
    import socket

    import writing_assistant.app.main as main_module
    from writing_assistant.app.server import main

    monkeypatch.setattr(main_module, "ALLOW_CUSTOM_ENV_VARS", True)
    main()

    lines = [call[0][0] for call in mock_print.call_args_list if call[0]]
    access = next(line for line in lines if "Access your writing assistant at:" in line)
    assert "0.0.0.0" not in access
    assert f"http://{socket.gethostname()}:8001/" in access
    assert any("Listening on all interfaces (0.0.0.0)" in line for line in lines)
    assert any("Custom environment variables are disabled" in line for line in lines)
    # The bind address itself is unchanged.
    assert mock_uvicorn_run.call_args.kwargs["host"] == "0.0.0.0"


@patch("writing_assistant.app.server.asyncio.run")
@patch("sys.argv", ["server.py", "--init-db"])
def test_main_init_db_flag(mock_asyncio_run):
    """Test main function with --init-db flag."""
    from writing_assistant.app.server import main

    main()

    # Verify asyncio.run was called for database initialization
    mock_asyncio_run.assert_called_once()


def test_main_script_execution():
    """Test the if __name__ == '__main__' block."""
    # Simple test that verifies the main function exists and is callable
    from writing_assistant.app.server import main

    assert callable(main)


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("builtins.print")
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_prints_web_page_urls(mock_port_check, mock_print, mock_uvicorn_run):
    """The banner must point at the HTML pages, not the JSON API endpoints."""
    from writing_assistant.app.server import main

    main()

    print_calls = [call[0][0] for call in mock_print.call_args_list if call[0]]

    register_lines = [c for c in print_calls if "Register a new account at:" in c]
    login_lines = [c for c in print_calls if "Login at:" in c]

    assert register_lines
    assert register_lines[0].endswith("/register")
    assert "/auth/register" not in register_lines[0]
    assert login_lines
    assert login_lines[0].endswith("/login")
    assert "/auth/jwt/login" not in login_lines[0]


@patch("writing_assistant.app.server.uvicorn.run")
def test_main_port_in_use_detected_on_any_address_family(
    mock_uvicorn_run, capsys, monkeypatch
):
    """A conflict on 127.0.0.1 must abort even when getaddrinfo resolves
    localhost to ::1 first (uvicorn binds every resolved address, so the
    IPv4 conflict would still kill it after the banner)."""
    from writing_assistant.app.server import main

    monkeypatch.setattr(server, "port_in_use", _REAL_PORT_IN_USE)

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]

        real_getaddrinfo = socket.getaddrinfo

        def ipv6_first(host, *args, **kwargs):
            infos = real_getaddrinfo(host, *args, **kwargs)
            v6 = (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", port, 0, 0))
            return [v6] + [info for info in infos if info[0] == socket.AF_INET]

        with (
            patch(
                "writing_assistant.app.server.socket.getaddrinfo",
                side_effect=ipv6_first,
            ),
            patch("sys.argv", ["server.py", "--port", str(port)]),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "already in use" in captured.err
        assert "Writing Assistant Server" not in captured.out
        mock_uvicorn_run.assert_not_called()
    finally:
        blocker.close()


@patch("writing_assistant.app.server.uvicorn.run")
def test_main_port_in_use_fails_before_banner(mock_uvicorn_run, capsys, monkeypatch):
    """When the port is already taken, main must exit with a clear error
    instead of printing the success banner and letting uvicorn fail later."""
    from writing_assistant.app.server import main

    monkeypatch.setattr(server, "port_in_use", _REAL_PORT_IN_USE)

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("localhost", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]

        with (
            patch("sys.argv", ["server.py", "--port", str(port)]),
            pytest.raises(SystemExit) as excinfo,
        ):
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert f"cannot bind to localhost:{port}" in captured.err
        assert "already in use" in captured.err
        assert "--port" in captured.err
        # The success banner must not have been printed.
        assert "Writing Assistant Server" not in captured.out
        mock_uvicorn_run.assert_not_called()
    finally:
        blocker.close()


# --------------------------------------------------------------------------
# EmbeddedServer: the server the TUI starts for itself (--standalone)
# --------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_port_in_use_reports_a_listening_socket():
    # The autouse fixture stubs the module attribute; probe the real thing.
    port_in_use = _REAL_PORT_IN_USE

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        assert port_in_use("127.0.0.1", port)
    finally:
        blocker.close()
    assert not port_in_use("127.0.0.1", port)


def test_embedded_server_serves_over_loopback_and_logs_to_file(tmp_path, capfd):
    """The embedded server answers HTTP on the requested port, writes its
    log to the given file rather than the terminal (which the TUI owns),
    and stops when asked."""
    import httpx

    from writing_assistant.app.server import EmbeddedServer

    port = _free_port()
    log_path = tmp_path / "server.log"
    server = EmbeddedServer("127.0.0.1", port, log_path=log_path)
    assert server.url == f"http://127.0.0.1:{port}"
    assert not server.is_running

    server.start()
    try:
        assert server.is_running
        response = httpx.get(f"{server.url}/auth/check")
        assert response.status_code == 401  # up, and asking for a token
    finally:
        server.stop()

    assert not server.is_running
    text = log_path.read_text()
    assert "Uvicorn running on" in text
    assert "Finished server process" in text
    out, err = capfd.readouterr()
    assert out == ""
    assert err == ""
    # The file handler is detached again so later loggers don't inherit it.
    import logging

    assert not any(
        isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path)
        for h in logging.getLogger().handlers
    )


def test_embedded_server_start_fails_clearly_when_port_is_taken(tmp_path):
    from writing_assistant.app.server import EmbeddedServer

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]
        log_path = tmp_path / "server.log"
        server = EmbeddedServer("127.0.0.1", port, log_path=log_path)
        with pytest.raises(RuntimeError) as excinfo:
            server.start()
        assert str(port) in str(excinfo.value)
        assert str(log_path) in str(excinfo.value)
        assert not server.is_running
    finally:
        blocker.close()


def test_embedded_server_is_a_context_manager(tmp_path):
    import httpx

    from writing_assistant.app.server import EmbeddedServer

    port = _free_port()
    with EmbeddedServer("127.0.0.1", port, log_path=tmp_path / "s.log") as server:
        assert server.is_running
        assert httpx.get(f"{server.url}/docs").status_code == 200
    assert not server.is_running


# --- browser auto-open --------------------------------------------------------


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_main_opens_browser_by_default(mock_uvicorn_run, browser_launches, capsys):
    server.main()

    assert browser_launches == [("localhost", 8001)]
    assert "Opening in your web browser" in capsys.readouterr().out


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--no-browser"])
def test_main_no_browser_flag(mock_uvicorn_run, browser_launches, capsys):
    server.main()

    assert browser_launches == []
    assert "Opening in your web browser" not in capsys.readouterr().out
    mock_uvicorn_run.assert_called_once()


def test_launch_browser_opens_once_server_accepts(monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", lambda url: opened.append(url))

    # A listening socket stands in for the running server.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        _REAL_LAUNCH_BROWSER("127.0.0.1", port, timeout=3.0)
        deadline = time.monotonic() + 3.0
        while not opened and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        listener.close()

    assert opened == [f"http://127.0.0.1:{port}/"]


def test_launch_browser_does_not_open_when_server_never_starts(monkeypatch):
    opened = []
    monkeypatch.setattr(server.webbrowser, "open", lambda url: opened.append(url))

    # Reserve a port, then close it so nothing is listening there.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    _REAL_LAUNCH_BROWSER("127.0.0.1", port, timeout=0.4)
    time.sleep(0.8)

    assert opened == []


def test_browser_url_maps_wildcard_bind_to_loopback():
    assert server._browser_url("0.0.0.0", 8001) == "http://127.0.0.1:8001/"
    assert server._browser_url("localhost", 8001) == "http://localhost:8001/"


# --- already-running detection ------------------------------------------------


class _HealthHandler(http.server.BaseHTTPRequestHandler):
    payload: dict[str, str] = {}  # noqa: RUF012 - swapped per test via monkeypatch

    def do_GET(self):
        body = json.dumps(self.payload).encode()
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def health_server():
    """A loopback HTTP server answering /health with a configurable payload."""
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_running_instance_url_recognises_this_app(health_server, monkeypatch):
    monkeypatch.setattr(
        _HealthHandler, "payload", {"app": server.DIST_NAME, "version": "1.2.3"}
    )
    port = health_server.server_address[1]

    assert _REAL_RUNNING_INSTANCE_URL("127.0.0.1", port) == (
        f"http://127.0.0.1:{port}/"
    )


def test_running_instance_url_ignores_other_programs(health_server, monkeypatch):
    monkeypatch.setattr(_HealthHandler, "payload", {"app": "something-else"})
    port = health_server.server_address[1]

    assert _REAL_RUNNING_INSTANCE_URL("127.0.0.1", port) is None


def test_running_instance_url_when_nothing_listens():
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    assert _REAL_RUNNING_INSTANCE_URL("127.0.0.1", port, timeout=0.5) is None


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_main_already_running_opens_browser_and_exits(
    mock_uvicorn_run, monkeypatch, capsys
):
    """A second launch must not fail on the busy port: open the running one."""
    opened = []
    monkeypatch.setattr(
        server, "_running_instance_url", lambda host, port: "http://localhost:8001/"
    )
    monkeypatch.setattr(server.webbrowser, "open", lambda url: opened.append(url))

    server.main()

    assert opened == ["http://localhost:8001/"]
    mock_uvicorn_run.assert_not_called()
    out = capsys.readouterr().out
    assert "already running at http://localhost:8001/" in out
    assert "Writing Assistant Server" not in out  # no misleading start banner


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--no-browser"])
def test_main_already_running_respects_no_browser(
    mock_uvicorn_run, monkeypatch, capsys
):
    opened = []
    monkeypatch.setattr(
        server, "_running_instance_url", lambda host, port: "http://localhost:8001/"
    )
    monkeypatch.setattr(server.webbrowser, "open", lambda url: opened.append(url))

    server.main()

    assert opened == []
    mock_uvicorn_run.assert_not_called()
    assert "already running" in capsys.readouterr().out


# --- port fallback ------------------------------------------------------------


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_main_falls_back_when_default_port_is_held_by_another_program(
    mock_uvicorn_run, monkeypatch, browser_launches, capsys
):
    monkeypatch.setattr(server, "port_in_use", lambda host, port: port == 8001)

    server.main()

    assert mock_uvicorn_run.call_args.kwargs["port"] == 8002
    assert browser_launches == [("localhost", 8002)]
    out = capsys.readouterr().out
    assert "Port 8001 is in use by another program; using port 8002" in out
    assert "http://localhost:8002/" in out


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--port", "8001"])
def test_main_explicit_port_in_use_still_fails(mock_uvicorn_run, monkeypatch, capsys):
    monkeypatch.setattr(server, "port_in_use", lambda host, port: True)

    with pytest.raises(SystemExit) as excinfo:
        server.main()

    assert excinfo.value.code == 1
    assert "already in use" in capsys.readouterr().err
    mock_uvicorn_run.assert_not_called()


@patch.dict(os.environ, {"WRITING_ASSISTANT_PORT": "8001"})
@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_main_env_port_counts_as_explicit(mock_uvicorn_run, monkeypatch):
    monkeypatch.setattr(server, "port_in_use", lambda host, port: port == 8001)

    with pytest.raises(SystemExit):
        server.main()

    mock_uvicorn_run.assert_not_called()


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_main_reports_when_no_nearby_port_is_free(
    mock_uvicorn_run, monkeypatch, capsys
):
    monkeypatch.setattr(server, "port_in_use", lambda host, port: True)

    with pytest.raises(SystemExit) as excinfo:
        server.main()

    assert excinfo.value.code == 1
    assert "8001-8021 are all in use" in capsys.readouterr().err
    mock_uvicorn_run.assert_not_called()


# --- banner: the terminal-interface line and the JWT-secret warning ------------


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_banner_tui_command_is_bare_on_the_default_port(mock_uvicorn_run, capsys):
    """`writing-assistant-tui` already looks for localhost:8001, so the plain
    command is right there and the banner should not add noise."""
    server.main()

    line = next(
        ln for ln in capsys.readouterr().out.splitlines() if "Terminal interface" in ln
    )
    assert "`writing-assistant-tui`" in line
    assert "--server" not in line


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_banner_tui_command_names_the_port_after_a_fallback(
    mock_uvicorn_run, monkeypatch, capsys
):
    """A newcomer whose port fell back follows the banner; the bare command
    would point the terminal interface at whatever holds 8001."""
    monkeypatch.setattr(server, "port_in_use", lambda host, port: port == 8001)

    server.main()

    out = capsys.readouterr().out
    line = next(ln for ln in out.splitlines() if "Terminal interface" in ln)
    assert "writing-assistant-tui --server http://localhost:8002" in line


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--port", "8080"])
def test_banner_tui_command_names_an_explicit_port(mock_uvicorn_run, capsys):
    server.main()

    line = next(
        ln for ln in capsys.readouterr().out.splitlines() if "Terminal interface" in ln
    )
    assert "writing-assistant-tui --server http://localhost:8080" in line


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0"])
def test_banner_tui_command_names_the_host_for_a_wildcard_bind(
    mock_uvicorn_run, capsys
):
    server.main()

    line = next(
        ln for ln in capsys.readouterr().out.splitlines() if "Terminal interface" in ln
    )
    assert f"--server http://{socket.gethostname()}:8001" in line


def test_reachable_beyond_this_machine_classifies_bind_hosts():
    assert server._reachable_beyond_this_machine("0.0.0.0")  # nosec B104
    assert server._reachable_beyond_this_machine("")
    assert server._reachable_beyond_this_machine("192.168.1.10")
    assert server._reachable_beyond_this_machine("writing.example.com")
    assert not server._reachable_beyond_this_machine("localhost")
    assert not server._reachable_beyond_this_machine("127.0.0.1")
    assert not server._reachable_beyond_this_machine("::1")


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
def test_no_secret_warning_on_localhost(mock_uvicorn_run, monkeypatch, capsys):
    """The placeholder secret is harmless while only this machine can connect,
    and a warning nobody needs is a warning nobody reads."""
    monkeypatch.setattr(auth, "SECRET", auth.DEFAULT_SECRET)

    server.main()

    assert "WRITING_ASSISTANT_SECRET" not in capsys.readouterr().out


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0"])
def test_default_secret_warns_when_other_machines_can_connect(
    mock_uvicorn_run, monkeypatch, capsys
):
    monkeypatch.setattr(auth, "SECRET", auth.DEFAULT_SECRET)

    server.main()

    out = capsys.readouterr().out
    assert "WRITING_ASSISTANT_SECRET is unset" in out
    assert "every install shares" in out


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0"])
def test_no_secret_warning_once_the_secret_is_set(
    mock_uvicorn_run, monkeypatch, capsys
):
    monkeypatch.setattr(auth, "SECRET", "a-real-random-secret")

    server.main()

    assert "WRITING_ASSISTANT_SECRET" not in capsys.readouterr().out
