#!/usr/bin/env python3
"""User administration CLI.

This is a thin wrapper kept for running from a source checkout:

    python admin_users.py list

The real implementation lives in ``writing_assistant.admin_users`` and is
also installed as the ``writing-assistant-admin`` console command.
"""

import os
import sys

# Allow running from a source checkout without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from writing_assistant.admin_users import main  # noqa: E402

if __name__ == "__main__":
    main()
