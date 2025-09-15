"""Entry point for the writing assistant web server."""

import os
import uvicorn
from .main import app


def main():
    """Main entry point for the writing assistant server."""
    host = os.getenv("WRITING_ASSISTANT_HOST", "localhost")
    port = int(os.getenv("WRITING_ASSISTANT_PORT", "8001"))
    reload = os.getenv("WRITING_ASSISTANT_RELOAD", "false").lower() == "true"

    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()