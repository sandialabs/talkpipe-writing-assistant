"""Terminal user interface for the writing assistant.

A Textual application that talks to a running writing-assistant server over
its REST API, so it offers the same functionality as the web interface
(accounts, documents, snapshots, AI generation modes, settings) anywhere a
terminal is available -- an SSH session, a tmux window, a headless box.

Run it with ``writing-assistant-tui`` (or ``python -m writing_assistant.tui``).
"""
