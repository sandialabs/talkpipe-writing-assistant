"""Entry point for the writing assistant web server."""

import argparse
import asyncio
import os
import socket
import sys

import uvicorn

from .database import create_db_and_tables
from .main import app


def _fail_if_port_in_use(host: str, port: int) -> None:
    """Exit with a clear error if host:port is already taken.

    Without this check the success banner (URLs, database path) prints
    first and uvicorn's bind error only appears afterwards, which looks
    like the server started when it did not. Only a genuine
    "address already in use" aborts here; every other problem (bad host,
    unresolvable name, IPv6 quirks) is left for uvicorn to report.
    """
    import errno

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return  # let uvicorn report resolution problems
    family, socktype, proto, _, sockaddr = infos[0]
    try:
        sock = socket.socket(family, socktype, proto)
    except OSError:
        return
    with sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(sockaddr)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                return
            print(
                f"Error: cannot bind to {host}:{port} — the address is "
                f"already in use.\nStop the other process using the port, "
                f"or start with --port <other-port>.",
                file=sys.stderr,
            )
            raise SystemExit(1)


async def init_db():
    """Initialize the database."""
    print("Initializing database...")
    await create_db_and_tables()
    print("Database initialized successfully.")


def main():
    """Main entry point for the writing assistant server."""
    parser = argparse.ArgumentParser(
        description="Writing Assistant Web Server - Multi-User"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("WRITING_ASSISTANT_HOST", "localhost"),
        help="Host to bind to (default: localhost, or WRITING_ASSISTANT_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WRITING_ASSISTANT_PORT", "8001")),
        help="Port to bind to (default: 8001, or WRITING_ASSISTANT_PORT env var)",
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
        import writing_assistant.app.main as main_module

        main_module.ALLOW_CUSTOM_ENV_VARS = False

    # If --init-db flag is set, just initialize the database and exit
    if args.init_db:
        asyncio.run(init_db())
        print("Database initialization complete.")
        return

    # Fail fast (before the banner) if the port is already taken
    _fail_if_port_in_use(args.host, args.port)

    # Get database path for display
    from .database import get_database_url

    db_path = get_database_url().replace("sqlite+aiosqlite:///", "")

    print(f"\n🔐 Writing Assistant Server - Multi-User Edition", flush=True)
    print(
        f"📝 Access your writing assistant at: http://{args.host}:{args.port}/",
        flush=True,
    )
    print(
        f"🔑 Register a new account at: http://{args.host}:{args.port}/register",
        flush=True,
    )
    print(f"🔐 Login at: http://{args.host}:{args.port}/login", flush=True)
    print(f"📚 API documentation: http://{args.host}:{args.port}/docs", flush=True)
    print(f"💾 Database: {db_path}", flush=True)
    print("=" * 80, flush=True)
    sys.stdout.flush()

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
