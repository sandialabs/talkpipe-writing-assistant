"""Entry point for the writing assistant web server."""

import argparse
import os
import asyncio
import uvicorn
from .main import app
from .database import create_db_and_tables


async def init_db():
    """Initialize the database."""
    print("Initializing database...")
    await create_db_and_tables()
    print("Database initialized successfully.")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    await init_db()


def main():
    """Main entry point for the writing assistant server."""
    parser = argparse.ArgumentParser(description="Writing Assistant Web Server - Multi-User")
    parser.add_argument(
        "--host",
        default=os.getenv("WRITING_ASSISTANT_HOST", "localhost"),
        help="Host to bind to (default: localhost, or WRITING_ASSISTANT_HOST env var)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("WRITING_ASSISTANT_PORT", "8001")),
        help="Port to bind to (default: 8001, or WRITING_ASSISTANT_PORT env var)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("WRITING_ASSISTANT_RELOAD", "false").lower() == "true",
        help="Enable auto-reload (default: false, or WRITING_ASSISTANT_RELOAD env var)"
    )
    parser.add_argument(
        "--disable-custom-env-vars",
        action="store_true",
        default=False,
        help="Disable custom environment variables from the UI (security feature)"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        default=False,
        help="Initialize database and exit"
    )

    args = parser.parse_args()

    # Set custom environment variables flag
    if args.disable_custom_env_vars:
        import writing_assistant.app.main as main_module
        main_module.ALLOW_CUSTOM_ENV_VARS = False

    # If --init-db flag is set, just initialize the database and exit
    if args.init_db:
        asyncio.run(init_db())
        print("Database initialization complete.")
        return

    print(f"\n🔐 Writing Assistant Server - Multi-User Edition")
    print(f"📝 Access your writing assistant at: http://{args.host}:{args.port}/")
    print(f"🔑 Register a new account at: http://{args.host}:{args.port}/auth/register")
    print(f"🔐 Login at: http://{args.host}:{args.port}/auth/jwt/login")
    print(f"📚 API documentation: http://{args.host}:{args.port}/docs")
    print("=" * 80)

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()