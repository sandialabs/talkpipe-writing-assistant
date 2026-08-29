---
name: Release Checklist
about: Steps for doing a new release (see RELEASING.md for detail)
title: Release vX.Y.Z
labels: ''
assignees: ''

---

Assumes the TalkPipe release this depends on is already out and working.
The application itself must be tested by hand — the suite is not enough.

- [ ] `main` up to date, CI green, working tree clean
- [ ] `talkpipe[all]` floor in `pyproject.toml` matches what this release needs (`uv lock` if changed)
- [ ] Alembic migration committed for any model change
- [ ] CHANGELOG: `## Unreleased` → `## X.Y.Z (YYYY-MM-DD)`, fresh empty section above; merged via MR
- [ ] Build the wheel and install it into a **new** virtual environment
- [ ] Manual test — web UI (`writing-assistant`, scratch database, real Ollama model)
    - [ ] register, log out, log in; second account cannot see the first one's documents
    - [ ] AI Settings: Test Connection passes, wrong model reported, choice survives reload
    - [ ] Ideas / Rewrite / Improve / Proofread on a multi-section document; queued requests run in order; accept a suggestion
    - [ ] Save, Save As, Open, snapshot + Revert, Export + Import, Delete
    - [ ] `/docs` renders; `--disable-custom-env-vars` refuses per-user Connection fields
- [ ] Manual test — `writing-assistant-tui`: login, open/edit, `F5`–`F8` + `Ctrl+U`, `F3` settings round-trip with web UI, usable at 60×16 and in tmux
- [ ] Manual test — `writing-assistant-create-superuser` and `writing-assistant-admin` (list/info/reset-password/toggle-active)
- [ ] Manual test — container built with `APP_VERSION`, serves login page, reports the version, data survives restart
- [ ] Upgrade check: database from the previous release migrates on startup; user, document, snapshot intact
- [ ] Anything found: fix via MR, re-test
- [ ] Tag the merge commit on `main` (`git tag -a vX.Y.Z -m vX.Y.Z`) and push the tag
- [ ] Publish the release for the tag on GitHub (pre-release for betas/rcs); watch `publish-package` and the container build finish
- [ ] Verify: `pip install talkpipe-writing-assistant==X.Y.Z` in a fresh venv, `writing-assistant` serves http://localhost:8001; published container image starts and reports the version
