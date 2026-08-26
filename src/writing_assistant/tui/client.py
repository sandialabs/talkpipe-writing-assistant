"""Async REST client for the writing-assistant server.

Every TUI action goes through this class, which speaks exactly the HTTP API
the web front end uses (``app/main.py``). Nothing here touches the database
or TalkPipe directly, so the TUI can run on a different machine from the
server and shares the server's per-user document store with the web UI.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

import httpx

DEFAULT_SERVER_URL = "http://localhost:8001"


class ApiError(Exception):
    """A request the server refused, with a user-readable message."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthError(ApiError):
    """The session token is missing, expired, or rejected."""


def _detail_message(response: httpx.Response) -> str:
    """Turn a FastAPI error body into text a person can act on."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        code = detail.get("code")
        reason = detail.get("reason")
        if code == "REGISTER_INVALID_PASSWORD" and reason:
            return str(reason)
        return str(reason or code or detail)
    if isinstance(detail, list):
        # Pydantic validation errors: name the field, not the request part.
        messages = []
        for entry in detail:
            if not isinstance(entry, dict):
                continue
            loc = [str(part) for part in entry.get("loc", [])]
            if len(loc) > 1 and loc[0] == "body":
                loc = loc[1:]
            messages.append(f"{'.'.join(loc)}: {entry.get('msg')}")
        return "; ".join(messages)
    if isinstance(detail, str):
        return {
            "LOGIN_BAD_CREDENTIALS": "Incorrect email or password.",
            "LOGIN_USER_NOT_VERIFIED": "This account has not been verified.",
            "REGISTER_USER_ALREADY_EXISTS": "An account with that email already exists.",
            "Unauthorized": "Your session has expired. Please log in again.",
        }.get(detail, detail)
    if isinstance(body, dict) and body.get("message"):
        return str(body["message"])
    return f"HTTP {response.status_code}"


class WritingAssistantClient:
    """Thin async wrapper over the server's REST API.

    ``transport`` lets tests drive the FastAPI app in-process via
    ``httpx.ASGITransport``; production use leaves it ``None``.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_SERVER_URL,
        token: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http = httpx.AsyncClient(
            base_url=self.base_url, transport=transport, timeout=timeout
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- plumbing ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(
                method, path, headers=self._headers(), **kwargs
            )
        except httpx.ConnectError as exc:
            raise ApiError(
                f"Could not connect to the writing-assistant server at "
                f"{self.base_url}. Is it running? Start it with "
                "`writing-assistant`, or pass --server <url>."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApiError(
                f"The server at {self.base_url} did not answer in time."
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiError(f"Request to {self.base_url} failed: {exc}") from exc
        if response.status_code == 401:
            raise AuthError(_detail_message(response), 401)
        if response.status_code >= 400:
            raise ApiError(_detail_message(response), response.status_code)
        return response

    async def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError(f"Unexpected non-JSON reply from {path}") from exc
        if not isinstance(data, dict):
            raise ApiError(f"Unexpected reply from {path}")
        return data

    @staticmethod
    def _check_status(data: dict[str, Any], fallback: str) -> dict[str, Any]:
        """Raise on the ``{"status": "error", "message": ...}`` reply shape."""
        if data.get("status") == "error":
            raise ApiError(str(data.get("message") or fallback))
        if "error" in data and "status" not in data:
            raise ApiError(str(data["error"]))
        return data

    # -- accounts -----------------------------------------------------------

    async def login(self, email: str, password: str) -> str:
        """Log in and remember the bearer token. Returns the token."""
        self.token = None
        data = await self._json(
            "POST", "/auth/jwt/login", data={"username": email, "password": password}
        )
        token = data.get("access_token")
        if not token:
            raise ApiError("The server did not return an access token.")
        self.token = str(token)
        return self.token

    async def register(self, email: str, password: str) -> None:
        await self._json(
            "POST", "/auth/register", json={"email": email, "password": password}
        )

    async def logout(self) -> None:
        if self.token:
            with contextlib.suppress(ApiError):
                await self._request("POST", "/auth/jwt/logout")
        self.token = None

    async def check_auth(self) -> dict[str, Any]:
        """Return ``{"email": ..., "user_id": ...}``; raises AuthError if stale."""
        return await self._json("GET", "/auth/check")

    async def server_config(self) -> dict[str, Any]:
        return await self._json("GET", "/config")

    # -- preferences --------------------------------------------------------

    async def get_preferences(self) -> dict[str, Any]:
        data = self._check_status(
            await self._json("GET", "/user/preferences"),
            "Failed to load preferences",
        )
        prefs = data.get("preferences") or {}
        return prefs if isinstance(prefs, dict) else {}

    async def save_preferences(self, preferences: dict[str, Any]) -> None:
        self._check_status(
            await self._json(
                "POST", "/user/preferences", json={"preferences": preferences}
            ),
            "Failed to save preferences",
        )

    # -- documents ----------------------------------------------------------

    async def list_documents(self) -> list[dict[str, Any]]:
        data = self._check_status(
            await self._json("GET", "/documents/list"), "Failed to list documents"
        )
        files = data.get("files") or []
        return [f for f in files if isinstance(f, dict)]

    async def load_document(self, filename: str) -> dict[str, Any]:
        data = self._check_status(
            await self._json("GET", f"/documents/load/{filename}"),
            "Failed to load document",
        )
        document = data.get("document") or {}
        return document if isinstance(document, dict) else {}

    async def save_document(
        self, filename: str, document: dict[str, Any], *, save_as: bool = False
    ) -> str:
        """Save ``document`` under ``filename``; returns the server's message."""
        endpoint = "/documents/save-as" if save_as else "/documents/save"
        data = self._check_status(
            await self._json(
                "POST",
                endpoint,
                data={"filename": filename, "document_data": json.dumps(document)},
            ),
            "Failed to save document",
        )
        return str(data.get("message") or "Saved")

    async def delete_document(self, filename: str) -> str:
        data = self._check_status(
            await self._json("DELETE", f"/documents/delete/{filename}"),
            "Failed to delete document",
        )
        return str(data.get("message") or "Deleted")

    async def download_document(self, filename: str) -> str:
        """The raw JSON text of a saved document (for export)."""
        response = await self._request("GET", f"/documents/download/{filename}")
        return response.text

    # -- snapshots ----------------------------------------------------------

    async def create_snapshot(self, filename: str) -> str:
        data = self._check_status(
            await self._json("POST", f"/documents/snapshot/{filename}"),
            "Failed to create snapshot",
        )
        return str(data.get("message") or "Snapshot created")

    async def list_snapshots(self, filename: str) -> list[dict[str, Any]]:
        data = self._check_status(
            await self._json("GET", f"/documents/snapshots/{filename}"),
            "Failed to list snapshots",
        )
        snapshots = data.get("snapshots") or []
        return [s for s in snapshots if isinstance(s, dict)]

    async def load_snapshot(self, snapshot_name: str) -> dict[str, Any]:
        data = self._check_status(
            await self._json("GET", f"/documents/snapshot/load/{snapshot_name}"),
            "Failed to load snapshot",
        )
        document = data.get("document") or {}
        return document if isinstance(document, dict) else {}

    # -- AI -------------------------------------------------------------------

    async def generate_text(self, fields: dict[str, Any]) -> str:
        """POST /generate-text with the same form fields the web client sends."""
        form = {k: v for k, v in fields.items() if v is not None and v != ""}
        form.setdefault("environment_variables", "{}")
        data = await self._json("POST", "/generate-text", data=form)
        return str(data.get("generated_text") or "")

    async def test_connection(self, fields: dict[str, Any]) -> dict[str, Any]:
        """POST /ai/test-connection; returns the availability report."""
        form = {k: v for k, v in fields.items() if v is not None and v != ""}
        form.setdefault("environment_variables", "{}")
        try:
            return await self._json("POST", "/ai/test-connection", data=form)
        except ApiError as exc:
            if exc.status_code != 404:
                raise
            # Servers older than 1.0.0b1 have no /ai/test-connection route;
            # the bare "Not Found" that FastAPI returns reads like a failed
            # probe rather than a version mismatch.
            raise ApiError(
                f"The server at {self.base_url} does not support Test Connection "
                "(it needs writing-assistant 1.0.0b1 or newer). Upgrade the "
                "server — or pull a newer container image — to use it. "
                "Generation may still work with these settings.",
                404,
            ) from exc
