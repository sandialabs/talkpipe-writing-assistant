"""Connection testing for AI sources.

Modeled on the TalkPipe workbench settings dialog: build the prompt adapter
for the requested source/model and run a minimal, token-capped probe against
it, returning a structured availability report with an actionable reason on
failure instead of a bare boolean.
"""

import logging
from typing import Any

from talkpipe.llm.config import getPromptAdapter, getPromptSources
from talkpipe.util.config import get_config
from talkpipe.util.constants import (
    OLLAMA_SERVER_URL,
    TALKPIPE_MODEL_NAME,
    TALKPIPE_SOURCE,
)

logger = logging.getLogger(__name__)

# A real (but tiny) round trip: unlike a bare TCP check this verifies the
# credentials, the model name, and the generation path in one shot.
TEST_PROMPT = 'Reply with the single word "OK".'
TEST_MAX_TOKENS = 5

# How the UI's generic connection fields map onto the variables each
# provider's client actually reads. Ollama has no API key; the cloud SDKs
# read their key and base URL directly from these environment variables.
SOURCE_CONNECTION_ENV_VARS = {
    "ollama": {"server_url": "TALKPIPE_OLLAMA_SERVER_URL"},
    "openai": {"server_url": "OPENAI_BASE_URL", "api_key": "OPENAI_API_KEY"},
    "anthropic": {"server_url": "ANTHROPIC_BASE_URL", "api_key": "ANTHROPIC_API_KEY"},
}


def connection_env_overrides(
    source: str, server_url: str = "", api_key: str = ""
) -> dict[str, Any]:
    """Environment overrides for the generic Server URL / API Key fields.

    The fields are source-agnostic in the UI; this resolves them to the
    variables the selected source's client reads. An empty source falls back
    to the server's default TalkPipe source, mirroring generation.
    """
    source = (source or "").strip().lower()
    if not source:
        source = get_config().get(TALKPIPE_SOURCE, "") or ""
    mapping = SOURCE_CONNECTION_ENV_VARS.get(source, {})
    overrides = {}
    if server_url.strip() and "server_url" in mapping:
        overrides[mapping["server_url"]] = server_url.strip()
    if api_key.strip() and "api_key" in mapping:
        overrides[mapping["api_key"]] = api_key.strip()
    return overrides


def resolved_ollama_url() -> str:
    """The Ollama URL TalkPipe will actually use right now."""
    return get_config().get(OLLAMA_SERVER_URL) or "http://localhost:11434"


def _result(
    available: bool, source: str | None, model: str | None, reason: str | None
) -> dict[str, Any]:
    return {
        "available": available,
        "source": source,
        "model": model,
        "reason": reason,
        "known_sources": getPromptSources(),
    }


def _ollama_failure_hint(model: str, server_url_override: str = "") -> str:
    url = resolved_ollama_url()
    if server_url_override:
        # The URL in play came from the Server URL field in the dialog, so
        # the first thing to re-check is that field — not server-side
        # environment variables the user may not control.
        return (
            f" This test used the Server URL from your AI Settings "
            f"({server_url_override}) — double-check that value first "
            "(host, port, and http:// vs https://)."
        )
    hint = f" The server is currently configured to reach Ollama at {url}."
    if "localhost" in url or "127.0.0.1" in url:
        hint += (
            " If this app runs in a container, 'localhost' is the container "
            "itself, not the machine running Ollama — set the Server URL in "
            "AI Settings to your Ollama host, e.g. "
            "http://host.containers.internal:11434 when Ollama runs on the "
            "machine hosting the container."
        )
    return hint


# Substrings that mark a cloud-provider failure as a credentials problem.
_CREDENTIAL_ERROR_MARKERS = (
    "missing credentials",
    "api_key",
    "api key",
    "authentication",
    "unauthorized",
    "401",
)


def _cloud_failure_hint(
    source: str, reason: str, server_url_override: str, api_key_supplied: bool
) -> str:
    """UI-oriented remediation for OpenAI/Anthropic failures.

    The underlying SDK errors talk about environment variables and SDK
    parameters; a web-UI user's one-click fix is the API Key field sitting
    right above the Test Connection button, so mention that first.
    """
    hint = ""
    if any(marker in reason.lower() for marker in _CREDENTIAL_ERROR_MARKERS):
        if api_key_supplied:
            hint += (
                " The API Key entered in AI Settings was used for this "
                "test — double-check that key."
            )
        else:
            key_var = SOURCE_CONNECTION_ENV_VARS.get(source, {}).get("api_key")
            key_var_text = f" set {key_var}" if key_var else " set the API key"
            hint += (
                " Enter your key in the API Key field above (Settings → AI "
                f"Settings → Connection), or{key_var_text} on the server."
            )
    if server_url_override:
        hint += (
            f" This test used the Server URL from your AI Settings "
            f"({server_url_override})."
        )
    return hint


def test_connection(
    source: str,
    model: str,
    server_url_override: str = "",
    api_key_supplied: bool = False,
) -> dict[str, Any]:
    """Probe the given source/model and report availability.

    Empty source/model fall back to the server-level TalkPipe defaults,
    mirroring what LLMPrompt does during generation. ``server_url_override``
    and ``api_key_supplied`` describe connection values that came from the
    settings dialog (and were applied for this probe), so failure hints can
    point back at the right field. Returns a dict with ``available``,
    ``source``, ``model``, ``reason`` and ``known_sources``.
    """
    cfg = get_config()
    source = source or cfg.get(TALKPIPE_SOURCE, None)
    model = model or cfg.get(TALKPIPE_MODEL_NAME, None)

    if not source or not model:
        missing = []
        if not source:
            missing.append("AI Source")
        if not model:
            missing.append("Model name")
        return _result(
            False,
            source,
            model,
            f"No {' or '.join(missing)} configured. Choose them in Settings "
            "→ AI Settings, or ask the server administrator to configure a "
            "server default.",
        )

    known_sources = getPromptSources()
    if source not in known_sources:
        return _result(
            False,
            source,
            model,
            f"Unknown AI source '{source}'. Known sources: {', '.join(known_sources)}.",
        )

    try:
        adapter = getPromptAdapter(source)(model=model)
        adapter.complete_text_without_context(
            TEST_PROMPT, temperature=0.0, max_tokens=TEST_MAX_TOKENS
        )
    except Exception as e:
        logger.info(f"AI connection test failed for {source}/{model}: {e}")
        reason = str(e)
        if source == "ollama":
            reason += _ollama_failure_hint(model, server_url_override)
        elif source in ("openai", "anthropic"):
            reason += _cloud_failure_hint(
                source, reason, server_url_override, api_key_supplied
            )
        return _result(False, source, model, reason)

    return _result(True, source, model, None)
