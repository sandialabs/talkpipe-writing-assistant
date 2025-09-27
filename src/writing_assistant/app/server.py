"""Entry point for the writing assistant web server."""

import argparse
import os
import uvicorn
from .main import app


def main():
    """Main entry point for the writing assistant server."""
    parser = argparse.ArgumentParser(description="Writing Assistant Web Server")
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
        "--auth-token",
        help="Custom authentication token (default: auto-generated UUID)"
    )

    args = parser.parse_args()

    # Set custom token if provided, otherwise use auto-generated one
    if args.auth_token:
        import writing_assistant.app.main as main_module
        main_module.AUTH_TOKEN = args.auth_token
        AUTH_TOKEN = args.auth_token
    else:
        # Import here to get the auto-generated auth token
        from .main import AUTH_TOKEN

    print(f"\n🔐 Writing Assistant Server")
    print(f"📝 Access your writing assistant at: http://{args.host}:{args.port}/?token={AUTH_TOKEN}")
    print(f"🔑 Authentication token: {AUTH_TOKEN}")
    print("=" * 80)

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()