"""Entry point for the writing assistant web server."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import errno
import ipaddress
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from .. import DIST_NAME
from .database import create_db_and_tables
from .main import app

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8001
PORT_SEARCH_RANGE = 20
"""How many ports above the default to try when the default is taken."""


def port_in_use(host: str, port: int) -> bool:
    """True when something already listens on host:port.

    Only a genuine "address already in use" counts; every other problem
    (bad host, unresolvable name) is left for uvicorn to report. Every
    address the host resolves to is probed, because uvicorn binds all of
    them — a listener on 127.0.0.1 must be caught even when localhost
    resolves to ::1 first.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False  # let uvicorn report resolution problems
    for family, socktype, proto, _, sockaddr in infos:
        try:
            sock = socket.socket(family, socktype, proto)
        except OSError:
            continue
        with sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(sockaddr)
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    return True
    return False


def _fail_if_port_in_use(host: str, port: int) -> None:
    """Exit with a clear error if host:port is already taken.

    Without this check the success banner (URLs, database path) prints
    first and uvicorn's bind error only appears afterwards, which looks
    like the server started when it did not.
    """
    if port_in_use(host, port):
        print(
            f"Error: cannot bind to {host}:{port} — the address is "
            f"already in use.\nStop the other process using the port, "
            f"or start with --port <other-port>.",
            file=sys.stderr,
        )
        raise SystemExit(1)


class EmbeddedServer:
    """The writing-assistant server running in a background thread.

    Used by ``writing-assistant-tui --standalone`` so the terminal
    interface needs no separately started ``writing-assistant``. The
    server is the same FastAPI application, so it uses the same database
    (``WRITING_ASSISTANT_DB_PATH``), secret and AI configuration as a
    server started by hand — documents and logins are shared with one.

    The thread owns its own event loop; the caller's (Textual's) loop is
    untouched. Nothing is written to the terminal: uvicorn's log goes to
    ``log_path`` while the server runs, because the TUI owns the screen.
    """

    def __init__(self, host: str, port: int, *, log_path: Path | None = None) -> None:
        self.host = host
        self.port = port
        self.log_path = log_path
        self._server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_config=None, access_log=False)
        )
        self._thread = threading.Thread(
            target=self._run, name="writing-assistant-server", daemon=True
        )
        self._handler: logging.Handler | None = None
        self._previous_level: int | None = None

    def _run(self) -> None:
        # uvicorn calls sys.exit when it cannot bind; it has already logged
        # the reason, and start() reports the dead thread.
        with contextlib.suppress(SystemExit):
            self._server.run()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    def start(self, timeout: float = 30.0) -> None:
        """Start the server and return once it accepts connections.

        Raises ``RuntimeError`` if it fails to come up (the port taken in
        the meantime, a database problem, …); the log file has the reason.
        """
        self._attach_log()
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self._server.started:
            if not self._thread.is_alive():
                self._detach_log()
                where = f"; see {self.log_path}" if self.log_path else ""
                raise RuntimeError(
                    f"the writing-assistant server did not start on "
                    f"{self.host}:{self.port}{where}"
                )
            if time.monotonic() > deadline:
                self.stop()
                raise RuntimeError(
                    f"the writing-assistant server did not start on "
                    f"{self.host}:{self.port} within {timeout:g}s"
                )
            time.sleep(0.02)

    def stop(self, timeout: float = 10.0) -> None:
        """Ask the server to shut down and wait for the thread to finish."""
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout)
        self._detach_log()

    def __enter__(self) -> EmbeddedServer:
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _attach_log(self) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(self.log_path)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        # On the root logger so that application errors (logged under
        # ``writing_assistant``) land in the file too, and so that nothing
        # falls through to logging's last-resort stderr handler while the
        # TUI has the terminal.
        logging.getLogger().addHandler(handler)
        uvicorn_logger = logging.getLogger("uvicorn")
        self._previous_level = uvicorn_logger.level
        uvicorn_logger.setLevel(logging.INFO)
        self._handler = handler

    def _detach_log(self) -> None:
        if self._handler is None:
            return
        logging.getLogger().removeHandler(self._handler)
        self._handler.close()
        self._handler = None
        if self._previous_level is not None:
            logging.getLogger("uvicorn").setLevel(self._previous_level)
            self._previous_level = None


def _choose_port(host: str, requested: int | None) -> int:
    """The port to bind: the requested one, or the default with fallback.

    An explicit port (``--port`` or ``WRITING_ASSISTANT_PORT``) is honoured
    or fails loudly. With no explicit port, the default is used when free;
    when another program holds it, the next free port in a small range
    above it is used and announced, so a launch from a desktop entry still
    comes up instead of dying with a bind error.
    """
    if requested is not None:
        _fail_if_port_in_use(host, requested)
        return requested
    if not port_in_use(host, DEFAULT_PORT):
        return DEFAULT_PORT
    for candidate in range(DEFAULT_PORT + 1, DEFAULT_PORT + 1 + PORT_SEARCH_RANGE):
        if not port_in_use(host, candidate):
            print(
                f"Port {DEFAULT_PORT} is in use by another program; "
                f"using port {candidate} instead.",
                flush=True,
            )
            return candidate
    print(
        f"Error: ports {DEFAULT_PORT}-{DEFAULT_PORT + PORT_SEARCH_RANGE} are all "
        f"in use on {host}. Start with --port <other-port>.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _reachable_host(host: str) -> str:
    """Map a bind host to an address a client can actually reach.

    A wildcard bind address (0.0.0.0 / ::) isn't a routable target, so use the
    loopback address instead; any concrete host is used as-is. The wildcard
    literal here is only compared against, never bound to.
    """
    wildcard_hosts = ("", "0.0.0.0", "::")  # nosec B104 - comparison, not a bind
    return "127.0.0.1" if host in wildcard_hosts else host


def _browser_url(host: str, port: int) -> str:
    """Build the URL to open in a browser for the given bind host and port."""
    return f"http://{_reachable_host(host)}:{port}/"


def _launch_browser_when_ready(host: str, port: int, timeout: float = 15.0) -> None:
    """Open the app in a browser once the server accepts connections.

    Waits in a background daemon thread so we never open a dead page before the
    server is up, and so this does not block server startup. Failures (e.g. a
    headless container with no browser) are ignored.
    """
    url = _browser_url(host, port)
    connect_host = _reachable_host(host)

    def _wait_and_open() -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((connect_host, port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            return  # server never came up; nothing to open
        try:
            webbrowser.open(url)
        except Exception as exc:
            logger.debug("Could not open a browser for %s: %s", url, exc)

    threading.Thread(target=_wait_and_open, daemon=True).start()


def _running_instance_url(host: str, port: int, timeout: float = 1.0) -> str | None:
    """URL of a writing assistant already serving on host:port, else None.

    Asks the unauthenticated ``/health`` route and checks the application
    name it reports, so an unrelated program on the port is not mistaken
    for a running instance.
    """
    url = _browser_url(host, port)
    try:
        with urllib.request.urlopen(  # nosec B310 - http URL to a local port
            url + "health", timeout=timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(payload, dict) and payload.get("app") == DIST_NAME:
        return url
    return None


async def init_db() -> None:
    """Initialize the database."""
    print("Initializing database...")
    await create_db_and_tables()
    print("Database initialized successfully.")


def _binds_all_interfaces(host: str) -> bool:
    """True for the wildcard addresses (IPv4 or IPv6) and an empty host."""
    if not host:
        return True
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return False


def main() -> None:
    """Main entry point for the writing assistant server."""
    parser = argparse.ArgumentParser(
        description="Writing Assistant Web Server - Multi-User"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("WRITING_ASSISTANT_HOST", "localhost"),
        help="Host to bind to (default: localhost, or WRITING_ASSISTANT_HOST env var)",
    )
    env_port = os.getenv("WRITING_ASSISTANT_PORT")
    parser.add_argument(
        "--port",
        type=int,
        default=int(env_port) if env_port else None,
        help=(
            f"Port to bind to (default: {DEFAULT_PORT}, or WRITING_ASSISTANT_PORT "
            "env var). Without this option, the next free port above the "
            "default is used when another program holds it."
        ),
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the app in a web browser on startup.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("WRITING_ASSISTANT_RELOAD", "false").lower() == "true",
        help="Enable auto-reload (default: false, or WRITING_ASSISTANT_RELOAD env var)",
    )
    parser.add_argument(
        "--disable-custom-env-vars",
        action="store_true",
        default=False,
        help="Disable custom environment variables from the UI (security feature)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        default=False,
        help="Initialize database and exit",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("WRITING_ASSISTANT_DB_PATH"),
        help="Path to database file (default: ~/.writing_assistant/writing_assistant.db, or WRITING_ASSISTANT_DB_PATH env var)",
    )
    args = parser.parse_args()

    # Set database path environment variable if provided via CLI
    if args.db_path:
        os.environ["WRITING_ASSISTANT_DB_PATH"] = args.db_path

    # Set custom environment variables flag (the CLI flag forces it off;
    # otherwise the ALLOW_CUSTOM_ENV_VARS environment variable applies)
    if args.disable_custom_env_vars:
        from . import main as main_module

        main_module.ALLOW_CUSTOM_ENV_VARS = False

    # If --init-db flag is set, just initialize the database and exit
    if args.init_db:
        asyncio.run(init_db())
        print("Database initialization complete.")
        return

    # A second launch (a launcher clicked again, say) should not
    # fail: if this application already serves the port, just open it.
    running = _running_instance_url(
        args.host, args.port if args.port is not None else DEFAULT_PORT
    )
    if running:
        print(f"The Writing Assistant is already running at {running}", flush=True)
        if not args.no_browser:
            print("Opening it in your web browser...", flush=True)
            webbrowser.open(running)
        return

    # Fail fast (before the banner) if an explicit port is taken; fall back
    # to a nearby free port when the default is.
    port = _choose_port(args.host, args.port)

    # Get database path for display
    from .database import get_database_url

    db_path = get_database_url().replace("sqlite+aiosqlite:///", "")

    # A wildcard bind address is not a URL anyone can open: show the
    # machine's name in the URLs and say so.
    display_host = args.host
    if _binds_all_interfaces(args.host):
        display_host = socket.gethostname()
    base = f"http://{display_host}:{port}"

    print("\n🔐 Writing Assistant Server - Multi-User Edition", flush=True)
    print(f"📝 Access your writing assistant at: {base}/", flush=True)
    if display_host != args.host:
        print(
            f"🌐 Listening on all interfaces ({args.host}); from other machines "
            f"use this machine's name or IP address in place of {display_host}",
            flush=True,
        )
    print(f"🔑 Register a new account at: {base}/register", flush=True)
    print(f"🔐 Login at: {base}/login", flush=True)
    print(f"📚 API documentation: {base}/docs", flush=True)
    print(
        "💻 Terminal interface (no browser needed): run `writing-assistant-tui` "
        "in another terminal",
        flush=True,
    )
    print(f"💾 Database: {db_path}", flush=True)
    if not args.no_browser:
        print("🌐 Opening in your web browser...", flush=True)
    from . import main as main_module

    if not main_module.ALLOW_CUSTOM_ENV_VARS:
        print(
            "🔒 Custom environment variables are disabled: connection settings "
            "(server URL, API key) come from the server's environment",
            flush=True,
        )
    print("=" * 80, flush=True)
    sys.stdout.flush()

    if not args.no_browser:
        _launch_browser_when_ready(args.host, port)
    uvicorn.run(app, host=args.host, port=port, reload=args.reload)


if __name__ == "__main__":
    main()
