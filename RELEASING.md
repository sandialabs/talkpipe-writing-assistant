# Releasing the TalkPipe Writing Assistant

There is no version string to bump. The package version is derived from the
git tag by `setuptools_scm`, so a release is a tag plus a published release
that triggers the publish workflow.

This plan assumes the TalkPipe release the assistant depends on is already
out and working — its own release checklist covers the library. What it
does **not** assume is that the assistant still works on top of it: the
automated suite exercises the plumbing, but the application must be tried
by hand, against a real model, before the tag goes on. Do not skip the
manual section.

## Tag conventions

Tags are PEP 440 versions with a `v` prefix, on `main`:

| Kind              | Tag          | Example      |
|-------------------|--------------|--------------|
| Final             | `vX.Y.Z`     | `v1.0.0`     |
| Beta              | `vX.Y.ZbN`   | `v1.0.0b3`   |
| Release candidate | `vX.Y.ZrcN`  | `v1.0.0rc1`  |

Do not use other spellings (`v1.0.0-beta.1`, `v1.0.0.b1`) — they only make
version sorting harder. The assistant follows [semantic
versioning](https://semver.org/): PATCH for fixes only, MINOR for new
features that keep existing databases, settings, and the REST API working,
MAJOR for changes that break any of those.

## Steps

1. **Check the tree.** `main` is up to date, CI is green on it, and the
   working tree is clean.
2. **TalkPipe floor.** The `talkpipe[all]>=…` floor in `pyproject.toml`
   names the lowest TalkPipe release this version works with. If this
   release relies on newer library API, raise the floor (and `uv lock`)
   before anything else, so the changelog and the tests describe the same
   install.
3. **Database migrations.** If the models changed, an Alembic migration
   must be committed and the upgrade check below must pass against a
   database from the previous release.
4. **Changelog.** Rename the `## Unreleased` section in `CHANGELOG.md` to
   `## X.Y.Z (YYYY-MM-DD)` and add a fresh empty `## Unreleased` above it.
   Land that, together with any floor change, through the normal branch →
   merge request flow.
5. **Test the application by hand** (below) on the merge commit, in a fresh
   environment. Fix anything found through another merge request and come
   back to this step; do not tag a build that was not tried.
6. **Tag** the merge commit on `main` and push the tag:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

7. **Publish a release** for the tag on GitHub (*Releases → Draft a new
   release*). The CI workflow's
   `release: published` trigger runs `publish-package`, which builds the
   sdist and wheel, `twine check`s them, and uploads to PyPI with the
   `PYPI_API_TOKEN` repository secret; the container job (GitHub only)
   pushes `ghcr.io/sandialabs/talkpipe-writing-assistant:<version>` plus
   `latest` (final) or `experimental` (pre-release), for amd64 and arm64.
   Mark betas and release candidates as pre-releases. Watch the run finish.
8. **Verify** with a fresh environment:
   `pip install talkpipe-writing-assistant==X.Y.Z`,
   `python -c "from importlib.metadata import version; print(version('talkpipe-writing-assistant'))"`,
   then `writing-assistant` starts and http://localhost:8001/login loads.
   Pull the published container image and check it starts the same way and
   reports the release version.

Nothing is bumped afterwards; the next commit on `main` reports itself as
`X.Y.(Z+1).devN` automatically.

## Manual application test

Run this from a **wheel installed into a new virtual environment** (`python
-m build`, then `pip install dist/*.whl` in a fresh venv), not the editable
checkout — packaging mistakes (missing templates, static files, entry
points, migrations) only show up that way. Use a scratch database
(`--db-path` or `WRITING_ASSISTANT_DB_PATH`) and a working Ollama
(`TALKPIPE_OLLAMA_SERVER_URL`) so suggestions can be judged against a real
model. Exercise both interfaces — they share the server but have separate
code paths.

Web (`writing-assistant`, http://localhost:8001):

- Register a new account, log out, log in again; a second account cannot
  see the first one's documents.
- Settings → AI Settings: pick the Ollama source and a pulled model, **Test
  Connection** succeeds, a wrong model name is reported; **Save** and
  confirm the choice survives a reload. Set writing style / audience
  metadata.
- Write a document with several sections; each of **Ideas**, **Rewrite**,
  **Improve**, and **Proofread** returns something sensible for the section
  under the cursor; requests made while one is generating are queued and
  run in order; accepting a suggestion replaces the section text.
- Save, Save As, Open; a snapshot exists after saving and **Revert** to it
  restores the earlier text; Export a document and Import it back; Delete.
- `/docs` renders the API documentation.
- Start with `--disable-custom-env-vars` and confirm the per-user
  Connection fields are refused.

Terminal (`writing-assistant-tui` against the same server):

- Log in with the account above; the document list matches the web UI;
  open a document, edit, `F5`–`F8` produce suggestions, `Ctrl+U` applies
  one; `F3` AI Settings round-trips a model change that the web UI then
  shows; usable at 60×16 (the documented minimum) and in tmux.

Administration:

- `writing-assistant-create-superuser` creates an admin;
  `writing-assistant-admin list`, `info`, `reset-password`, and
  `toggle-active` behave (see `ADMIN_GUIDE.md`); a deactivated user cannot
  log in.

Container:

- `podman build --build-arg APP_VERSION="$(python3 -m setuptools_scm)" -t
  writing-assistant .` succeeds; `podman run --rm -p 8001:8001 -v
  <data>:/app/data writing-assistant` serves the login page, the version
  it reports matches the tag, and a document survives a container restart.

Upgrade check:

- Install the previous release, register a user and save a document with a
  snapshot, then upgrade to the wheel under test and start it against the
  same database — migrations run on startup, the user logs in, the document
  and snapshot are intact, and generation still works. Anything that cannot
  be migrated must be called out in the changelog.

## Downstream

Nothing in the suite pins the writing assistant. When a release changes the
REST API the terminal interface uses, the database schema, or the
command-line interface, say so prominently in the changelog and in the
README.
