"""Tests for the AI connection test feature (workbench-style availability check)."""

import os
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Core logic: writing_assistant.core.ai_connection.test_connection
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Stands in for a TalkPipe prompt adapter."""

    instances = []

    def __init__(self, model, **kwargs):
        self.model = model
        self.kwargs = kwargs
        self.probes = []
        FakeAdapter.instances.append(self)

    def complete_text_without_context(self, prompt, **kwargs):
        self.probes.append((prompt, kwargs))
        return "OK"


class BrokenAdapter(FakeAdapter):
    def complete_text_without_context(self, prompt, **kwargs):
        raise ConnectionError("connection refused by test double")


@pytest.fixture(autouse=True)
def _reset_fake_adapter():
    FakeAdapter.instances = []
    yield
    FakeAdapter.instances = []


def test_connection_success_with_explicit_source_and_model():
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=FakeAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
    ):
        result = ai_connection.test_connection("ollama", "llama3.1:8b")

    assert result["available"] is True
    assert result["source"] == "ollama"
    assert result["model"] == "llama3.1:8b"
    assert result["reason"] is None
    # The probe must actually have hit the adapter, with a capped generation.
    assert len(FakeAdapter.instances) == 1
    prompt, kwargs = FakeAdapter.instances[0].probes[0]
    assert kwargs.get("max_tokens") is not None


def test_connection_failure_classifies_unreachable_server():
    """A connection failure is reported as such, in the app's own words,
    without echoing the raw exception text (which may carry internal
    hostnames or other server-side details)."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=BrokenAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
    ):
        result = ai_connection.test_connection("ollama", "llama3.1:8b")

    assert result["available"] is False
    assert "Could not connect to the Ollama server" in result["reason"]
    assert "connection refused by test double" not in result["reason"]


class LeakyAdapter(FakeAdapter):
    def complete_text_without_context(self, prompt, **kwargs):
        raise RuntimeError("secret internal detail: /srv/private/path token=abc")


def test_connection_unexpected_failure_never_echoes_exception_text():
    """Unclassified failures name the error type (safe, and enough to search
    the server log for) but never the exception message."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=LeakyAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection("ollama", "llama3.1:8b")

    assert result["available"] is False
    assert "secret internal detail" not in result["reason"]
    assert "abc" not in result["reason"]
    assert "RuntimeError" in result["reason"]
    assert "server log" in result["reason"]


class MissingModelAdapter(FakeAdapter):
    def complete_text_without_context(self, prompt, **kwargs):
        # Mirrors the ResponseError TalkPipe re-raises for an Ollama 404.
        raise LookupError("Model 'llama3.1:8b' is not available on the Ollama server")


def test_connection_ollama_missing_model_suggests_pull():
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=MissingModelAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection("ollama", "llama3.1:8b")

    assert result["available"] is False
    assert "llama3.1:8b" in result["reason"]
    assert "ollama pull llama3.1:8b" in result["reason"]
    # A missing model is not a connectivity problem: no container/URL advice.
    assert "host.containers.internal" not in result["reason"]


def test_connection_unknown_source():
    from writing_assistant.core import ai_connection

    with patch.object(
        ai_connection,
        "getPromptSources",
        return_value=["ollama", "openai", "anthropic"],
    ):
        result = ai_connection.test_connection("nonsense", "some-model")

    assert result["available"] is False
    assert "nonsense" in result["reason"]
    assert "ollama" in result["reason"]


def test_connection_missing_source_and_model_without_server_default():
    from writing_assistant.core import ai_connection

    with patch.object(ai_connection, "get_config", return_value={}):
        result = ai_connection.test_connection("", "")

    assert result["available"] is False
    # The reason should point a web-UI user at the Settings dialog, not at
    # TalkPipe config files.
    assert "Settings" in result["reason"]


def test_connection_falls_back_to_server_default_model():
    from talkpipe.util.constants import TALKPIPE_MODEL_NAME, TALKPIPE_SOURCE

    from writing_assistant.core import ai_connection

    cfg = {TALKPIPE_SOURCE: "ollama", TALKPIPE_MODEL_NAME: "default-model"}
    with (
        patch.object(ai_connection, "get_config", return_value=cfg),
        patch.object(ai_connection, "getPromptAdapter", return_value=FakeAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
    ):
        result = ai_connection.test_connection("", "")

    assert result["available"] is True
    assert result["source"] == "ollama"
    assert result["model"] == "default-model"


def test_connection_ollama_failure_with_ui_server_url_points_at_field():
    """When the failing Ollama URL came from the Server URL field in the UI,
    the advice must point back at that field instead of steering the user
    toward server-side environment variables."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=BrokenAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection(
            "ollama",
            "llama3.1:8b",
            server_url_override="http://192.168.0.7:9999",
        )

    assert result["available"] is False
    assert "Server URL" in result["reason"]
    assert "http://192.168.0.7:9999" in result["reason"]


class MissingKeyAdapter(FakeAdapter):
    def __init__(self, model, **kwargs):
        super().__init__(model, **kwargs)
        raise RuntimeError(
            "Could not initialize the OpenAI client: Missing credentials. "
            "Please pass an `api_key` or set the `OPENAI_API_KEY` "
            "environment variable."
        )


def test_connection_cloud_missing_key_mentions_api_key_field():
    """A missing cloud key should point the user at the API Key field in the
    dialog (the one-click fix), not only at environment variables."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=MissingKeyAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["openai"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection("openai", "gpt-4o")

    assert result["available"] is False
    assert "API Key field" in result["reason"]
    assert "OPENAI_API_KEY" in result["reason"]
    # The SDK's own wording is not echoed - the app describes the failure.
    assert "Could not initialize the OpenAI client" not in result["reason"]
    assert "Authentication with OpenAI failed" in result["reason"]


def test_connection_cloud_bad_key_supplied_via_ui():
    """If the user did supply a key in the dialog and it still fails with a
    credential error, say so instead of asking them to enter one."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=MissingKeyAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["openai"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection(
            "openai", "gpt-4o", api_key_supplied=True
        )

    assert result["available"] is False
    assert "API Key entered in AI Settings" in result["reason"]


def test_connection_ollama_failure_mentions_container_hint():
    """When Ollama at a localhost URL is unreachable, the reason should
    explain that localhost inside a container is the container itself."""
    from writing_assistant.core import ai_connection

    with (
        patch.object(ai_connection, "getPromptAdapter", return_value=BrokenAdapter),
        patch.object(ai_connection, "getPromptSources", return_value=["ollama"]),
        patch.object(ai_connection, "get_config", return_value={}),
    ):
        result = ai_connection.test_connection("ollama", "llama3.1:8b")

    assert result["available"] is False
    assert "host.containers.internal" in result["reason"]


# ---------------------------------------------------------------------------
# API endpoint: POST /ai/test-connection
# ---------------------------------------------------------------------------


def test_endpoint_requires_authentication(client):
    response = client.post(
        "/ai/test-connection", data={"source": "ollama", "model": "x"}
    )
    assert response.status_code == 401


@patch("writing_assistant.app.main.ai_connection.test_connection")
def test_endpoint_returns_probe_result(mock_test, authenticated_client):
    mock_test.return_value = {
        "available": True,
        "source": "ollama",
        "model": "llama3.1:8b",
        "reason": None,
        "known_sources": ["ollama"],
    }
    response = authenticated_client.post(
        "/ai/test-connection",
        data={"source": "Ollama", "model": " llama3.1:8b "},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    # Source should be normalized (lowercased/stripped) like /generate-text.
    mock_test.assert_called_once_with(
        "ollama", "llama3.1:8b", server_url_override="", api_key_supplied=False
    )


@patch("writing_assistant.app.main.ai_connection.test_connection")
def test_endpoint_reports_ui_overrides_to_probe(mock_test, authenticated_client):
    """The probe is told which connection values came from the dialog so its
    failure hints can point back at the right field."""
    mock_test.return_value = {
        "available": False,
        "source": "ollama",
        "model": "llama3.1:8b",
        "reason": "nope",
        "known_sources": ["ollama"],
    }
    response = authenticated_client.post(
        "/ai/test-connection",
        data={
            "source": "ollama",
            "model": "llama3.1:8b",
            "server_url": "http://elsewhere:11434",
            "api_key": "sk-test",
        },
    )
    assert response.status_code == 200
    mock_test.assert_called_once_with(
        "ollama",
        "llama3.1:8b",
        server_url_override="http://elsewhere:11434",
        api_key_supplied=True,
    )


@patch("writing_assistant.app.main.ai_connection.test_connection")
def test_endpoint_ignores_ui_overrides_when_custom_env_vars_disabled(
    mock_test, authenticated_client
):
    """With ALLOW_CUSTOM_ENV_VARS off the fields are not applied, so the
    probe must not attribute the values to the dialog either."""
    from writing_assistant.app import main as main_module

    mock_test.return_value = {
        "available": True,
        "source": "ollama",
        "model": "llama3.1:8b",
        "reason": None,
        "known_sources": ["ollama"],
    }
    with patch.object(main_module, "ALLOW_CUSTOM_ENV_VARS", False):
        response = authenticated_client.post(
            "/ai/test-connection",
            data={
                "source": "ollama",
                "model": "llama3.1:8b",
                "server_url": "http://elsewhere:11434",
                "api_key": "sk-test",
            },
        )
    assert response.status_code == 200
    mock_test.assert_called_once_with(
        "ollama", "llama3.1:8b", server_url_override="", api_key_supplied=False
    )


@patch("writing_assistant.app.main.ai_connection.test_connection")
def test_endpoint_applies_environment_variables_temporarily(
    mock_test, authenticated_client
):
    seen = {}

    def record(source, model, **kwargs):
        seen["url"] = os.environ.get("TALKPIPE_OLLAMA_SERVER_URL")
        return {
            "available": True,
            "source": source,
            "model": model,
            "reason": None,
            "known_sources": [],
        }

    mock_test.side_effect = record
    assert "TALKPIPE_OLLAMA_SERVER_URL" not in os.environ

    response = authenticated_client.post(
        "/ai/test-connection",
        data={
            "source": "ollama",
            "model": "llama3.1:8b",
            "environment_variables": '{"TALKPIPE_OLLAMA_SERVER_URL": "http://elsewhere:11434"}',
        },
    )
    assert response.status_code == 200
    assert seen["url"] == "http://elsewhere:11434"
    # The variable must not leak past the request.
    assert "TALKPIPE_OLLAMA_SERVER_URL" not in os.environ


@patch("writing_assistant.app.main.ai_connection.test_connection")
def test_endpoint_server_url_field_maps_per_source(mock_test, authenticated_client):
    """The dedicated server_url field maps to the right variable for the
    selected source, without the user hand-crafting environment variables."""
    seen = {}

    def record(source, model, **kwargs):
        seen[source] = {
            "ollama_url": os.environ.get("TALKPIPE_OLLAMA_SERVER_URL"),
            "openai_url": os.environ.get("OPENAI_BASE_URL"),
        }
        return {
            "available": True,
            "source": source,
            "model": model,
            "reason": None,
            "known_sources": [],
        }

    mock_test.side_effect = record

    response = authenticated_client.post(
        "/ai/test-connection",
        data={
            "source": "ollama",
            "model": "llama3.1:8b",
            "server_url": "http://host.containers.internal:11434",
        },
    )
    assert response.status_code == 200
    assert seen["ollama"]["ollama_url"] == "http://host.containers.internal:11434"
    assert seen["ollama"]["openai_url"] is None

    response = authenticated_client.post(
        "/ai/test-connection",
        data={
            "source": "openai",
            "model": "gpt-4o",
            "server_url": "http://proxy.example:8080/v1",
        },
    )
    assert response.status_code == 200
    assert seen["openai"]["openai_url"] == "http://proxy.example:8080/v1"
    assert seen["openai"]["ollama_url"] is None

    # Nothing leaks past the requests.
    assert "TALKPIPE_OLLAMA_SERVER_URL" not in os.environ
    assert "OPENAI_BASE_URL" not in os.environ


# ---------------------------------------------------------------------------
# /generate-text: dedicated server_url / api_key fields
# ---------------------------------------------------------------------------


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text_server_url_field_ollama(
    mock_new_paragraph, authenticated_client
):
    seen = {}

    def record(**kwargs):
        seen["url"] = os.environ.get("TALKPIPE_OLLAMA_SERVER_URL")
        return "generated"

    mock_new_paragraph.side_effect = record

    response = authenticated_client.post(
        "/generate-text",
        data={
            "user_text": "hello",
            "source": "ollama",
            "model": "llama3.1:8b",
            "server_url": "http://host.containers.internal:11434",
        },
    )
    assert response.status_code == 200
    assert seen["url"] == "http://host.containers.internal:11434"
    assert "TALKPIPE_OLLAMA_SERVER_URL" not in os.environ


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text_api_key_field_anthropic(
    mock_new_paragraph, authenticated_client
):
    seen = {}

    def record(**kwargs):
        seen["key"] = os.environ.get("ANTHROPIC_API_KEY")
        seen["url"] = os.environ.get("ANTHROPIC_BASE_URL")
        return "generated"

    mock_new_paragraph.side_effect = record
    original_key = os.environ.get("ANTHROPIC_API_KEY")

    response = authenticated_client.post(
        "/generate-text",
        data={
            "user_text": "hello",
            "source": "anthropic",
            "model": "claude-sonnet-4-5",
            "api_key": "sk-ant-test-123",
            "server_url": "http://claude-proxy.example",
        },
    )
    assert response.status_code == 200
    assert seen["key"] == "sk-ant-test-123"
    assert seen["url"] == "http://claude-proxy.example"
    assert os.environ.get("ANTHROPIC_API_KEY") == original_key
    assert "ANTHROPIC_BASE_URL" not in os.environ


@patch("writing_assistant.app.main.cb.new_paragraph")
def test_generate_text_connection_fields_disabled_with_custom_env_vars(
    mock_new_paragraph, authenticated_client
):
    """server_url/api_key are part of the same trust surface as custom env
    vars: when the admin disables custom env vars, they are ignored too."""
    from writing_assistant.app import main as main_module

    seen = {}

    def record(**kwargs):
        seen["url"] = os.environ.get("TALKPIPE_OLLAMA_SERVER_URL")
        return "generated"

    mock_new_paragraph.side_effect = record

    with patch.object(main_module, "ALLOW_CUSTOM_ENV_VARS", False):
        response = authenticated_client.post(
            "/generate-text",
            data={
                "user_text": "hello",
                "source": "ollama",
                "model": "llama3.1:8b",
                "server_url": "http://host.containers.internal:11434",
            },
        )
    assert response.status_code == 200
    assert seen["url"] is None


def test_connection_env_overrides_resolves_default_source():
    """With no explicit source, the override maps using the server's default
    source from the TalkPipe configuration."""
    from talkpipe.util.constants import TALKPIPE_SOURCE

    from writing_assistant.core import ai_connection

    cfg = {TALKPIPE_SOURCE: "openai"}
    with patch.object(ai_connection, "get_config", return_value=cfg):
        overrides = ai_connection.connection_env_overrides(
            "", server_url="http://proxy.example/v1", api_key="sk-test"
        )
    assert overrides == {
        "OPENAI_BASE_URL": "http://proxy.example/v1",
        "OPENAI_API_KEY": "sk-test",
    }
