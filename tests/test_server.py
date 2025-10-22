"""Tests for the server.py module."""

import os
from unittest.mock import MagicMock, patch

import pytest


@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py'])
def test_main_default_arguments(mock_uvicorn_run):
    """Test main function with default arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with default values
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs['host'] == 'localhost'
    assert kwargs['port'] == 8001
    assert kwargs['reload'] == False


@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py', '--host', '0.0.0.0', '--port', '9000', '--reload'])
def test_main_custom_arguments(mock_uvicorn_run):
    """Test main function with custom arguments."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with custom values
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs['host'] == '0.0.0.0'
    assert kwargs['port'] == 9000
    assert kwargs['reload'] == True


@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py', '--disable-custom-env-vars'])
def test_main_disable_custom_env_vars(mock_uvicorn_run):
    """Test main function with custom env vars disabled."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called
    mock_uvicorn_run.assert_called_once()


@patch.dict(os.environ, {
    'WRITING_ASSISTANT_HOST': '192.168.1.100',
    'WRITING_ASSISTANT_PORT': '8080',
    'WRITING_ASSISTANT_RELOAD': 'true'
})
@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py'])
def test_main_environment_variables(mock_uvicorn_run):
    """Test main function with environment variables."""
    from writing_assistant.app.server import main

    main()

    # Verify uvicorn.run was called with environment variable values
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs['host'] == '192.168.1.100'
    assert kwargs['port'] == 8080
    assert kwargs['reload'] == True


@patch.dict(os.environ, {'WRITING_ASSISTANT_RELOAD': 'false'})
@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py'])
def test_main_reload_false_environment(mock_uvicorn_run):
    """Test main function with reload disabled via environment variable."""
    from writing_assistant.app.server import main

    main()

    # Verify reload is false
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs['reload'] == False


@patch.dict(os.environ, {'WRITING_ASSISTANT_RELOAD': 'TRUE'})
@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py'])
def test_main_reload_true_case_insensitive(mock_uvicorn_run):
    """Test main function with reload enabled (case insensitive)."""
    from writing_assistant.app.server import main

    main()

    # Verify reload is true (case insensitive)
    mock_uvicorn_run.assert_called_once()
    args, kwargs = mock_uvicorn_run.call_args
    assert kwargs['reload'] == True


@patch('writing_assistant.app.server.uvicorn.run')
@patch('sys.argv', ['server.py'])
@patch('builtins.print')
def test_main_prints_server_info(mock_print, mock_uvicorn_run):
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


@patch('writing_assistant.app.server.asyncio.run')
@patch('sys.argv', ['server.py', '--init-db'])
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