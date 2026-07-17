"""Tests for the server.py module."""

import os
from unittest.mock import MagicMock, patch

import pytest


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_default_arguments(mock_port_check, mock_uvicorn_run):
    """Test main function with default arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with default values
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 8001
    assert kwargs["reload"] == False


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--host", "0.0.0.0", "--port", "9000", "--reload"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_custom_arguments(mock_port_check, mock_uvicorn_run):
    """Test main function with custom arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with custom values
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 9000
    assert kwargs["reload"] == True


@patch("writing_assistant.app.server.uvicorn.run")
@patch("sys.argv", ["server.py", "--disable-custom-env-vars"])
@patch("writing_assistant.app.server._fail_if_port_in_use")
def test_main_disable_custom_env_vars(mock_port_check, mock_uvicorn_run):
    """Test main function with custom env vars disabled."""
    from writing_assistant.app.server import main

    main()

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
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["host"] == "192.168.1.100"
    assert kwargs["port"] == 8080
    assert kwargs["reload"] == True


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
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["reload"] == False


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
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs["reload"] == True


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

    assert register_lines and register_lines[0].endswith("/register")
    assert "/auth/register" not in register_lines[0]
    assert login_lines and login_lines[0].endswith("/login")
    assert "/auth/jwt/login" not in login_lines[0]


@patch("writing_assistant.app.server.uvicorn.run")
def test_main_port_in_use_detected_on_any_address_family(mock_uvicorn_run, capsys):
    """A conflict on 127.0.0.1 must abort even when getaddrinfo resolves
    localhost to ::1 first (uvicorn binds every resolved address, so the
    IPv4 conflict would still kill it after the banner)."""
    import socket

    from writing_assistant.app.server import main

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

        with patch(
            "writing_assistant.app.server.socket.getaddrinfo",
            side_effect=ipv6_first,
        ):
            with patch("sys.argv", ["server.py", "--port", str(port)]):
                with pytest.raises(SystemExit) as excinfo:
                    main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "already in use" in captured.err
        assert "Writing Assistant Server" not in captured.out
        mock_uvicorn_run.assert_not_called()
    finally:
        blocker.close()


@patch("writing_assistant.app.server.uvicorn.run")
def test_main_port_in_use_fails_before_banner(mock_uvicorn_run, capsys):
    """When the port is already taken, main must exit with a clear error
    instead of printing the success banner and letting uvicorn fail later."""
    import socket

    from writing_assistant.app.server import main

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        blocker.bind(("localhost", 0))
        blocker.listen(1)
        port = blocker.getsockname()[1]

        with patch("sys.argv", ["server.py", "--port", str(port)]):
            with pytest.raises(SystemExit) as excinfo:
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
