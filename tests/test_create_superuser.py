"""Tests for the create-superuser console command helpers."""


def test_login_url_uses_configured_host_and_port(monkeypatch):
    """The closing hint must reflect the server's actual host/port
    configuration instead of a hardcoded http://localhost:8001."""
    from writing_assistant import create_superuser

    monkeypatch.setenv("WRITING_ASSISTANT_HOST", "myhost.example")
    monkeypatch.setenv("WRITING_ASSISTANT_PORT", "8705")
    assert create_superuser.login_url() == "http://myhost.example:8705/login"


def test_login_url_defaults_match_server_defaults(monkeypatch):
    from writing_assistant import create_superuser

    monkeypatch.delenv("WRITING_ASSISTANT_HOST", raising=False)
    monkeypatch.delenv("WRITING_ASSISTANT_PORT", raising=False)
    assert create_superuser.login_url() == "http://localhost:8001/login"
