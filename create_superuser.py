#!/usr/bin/env python3
"""Create the first superuser account.

This is a thin wrapper kept for running from a source checkout:

    python create_superuser.py

The real implementation lives in ``writing_assistant.create_superuser`` and
is also installed as the ``writing-assistant-create-superuser`` console
command.
"""

import os
import sys

# Allow running from a source checkout without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from writing_assistant.create_superuser import main  # noqa: E402

if __name__ == "__main__":
    main()
