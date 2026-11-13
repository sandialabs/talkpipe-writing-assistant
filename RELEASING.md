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

   Then advance `stable`, the repository's default branch, to the release.
   `stable` only ever points at a full release, so skip this for betas and
   release candidates:

   ```bash
   git push origin vX.Y.Z^{commit}:stable
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
   reports the release version, and `curl http://localhost:8001/health`
   reports it once started.

Nothing is bumped afterwards; the next commit on `main` reports itself as
`X.Y.(Z+1).devN` automatically.

## Manual application test

Run this from a **wheel installed into a new virtual environment** (`python
-m build`, then `pip install dist/*.whl` in a fresh venv), not the editable
checkout — packaging mistakes (missing templates, static files, entry
points, migrations) only show up that way. Use a scratch database
(`--db-path` or `WRITING_ASSISTANT_DB_PATH`) and a real model from any
supported source so suggestions can be judged — Ollama
(`TALKPIPE_OLLAMA_SERVER_URL`) is the keyless choice; OpenAI or Anthropic
work as well. Exercise both interfaces — they share the server but have
separate code paths.

Web (`writing-assistant`, http://localhost:8001):

- Register a new account, log out, log in again; a second account cannot
  see the first one's documents.
- Settings → AI Settings: pick that source and a model it offers, **Test
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

## Security hotfix releases

Everything above describes a **regular release**: it is cut from `main`
and **a person reviews it**. An agent may prepare one (the changelog, the
merge request, the test runs), but a person reads the result and decides to
tag and publish it. That holds for every release except the one kind
described here.

A **security hotfix** may be carried out by an agent from start to finish,
without review, and only when all of this is true:

- its purpose is to clear the security advisories GitHub reports against
  `stable` (Dependabot alerts);
- every one of them is cleared by raising a dependency's lower bound in
  `pyproject.toml` and re-locking `uv.lock`, with no change under `src/`;
- beyond the floors it contains at most corrections to documentation and
  to code snippets, examples or tutorials that the upgrade made inaccurate.

Anything else is not a hotfix: a change to the source, a new feature, an
advisory with no patched version, a code-scanning or container-scan finding,
a floor that another dependency's cap forbids. That work goes through
`main` as a regular release, with human review. This autonomous procedure
never applies to a regular release.

A hotfix differs from the steps above in these points and no others:

1. **Branch.** It branches off `stable`, not `main`, as
   `chore/security-floors-YYYYMMDD`: the last release plus the floors, and
   nothing from development.
2. **Version.** The next PATCH after the release `stable` points at.
3. **Checks.** Every step above that comes before tagging still applies, on
   that branch: the changelog, the tests, and the manual application test,
   which the agent carries out itself against the wheel under test. Two
   more: every version the lock moves to must have been on PyPI for at
   least three days, and the package must still install together with the
   released TalkPipe it depends on (nothing in the suite depends on the
   assistant).
4. **CI.** The branch's final commit must pass on Gitea **and** on GitHub
   before `stable` moves. A merge request into `stable` starts no run; the
   evidence is the push run of the `chore/**` branch.
5. **Merge, tag, publish.** Only then is `stable` advanced, to the same
   commit on both hosts. The tag goes on that commit on `stable` rather than
   on `main`, and the GitHub release is published as in step 7.
6. **Afterwards** `stable` is merged back into `main` through a merge
   request, so `main` carries the tag and the floors.

The agent stops and hands the release to a person as soon as one of the
conditions fails, CI fails for a reason that is not an infrastructure fault,
or the testing turns up anything beyond the corrections named above.

## Downstream

Nothing in the suite pins the writing assistant. When a release changes the
REST API the terminal interface uses, the database schema, or the
command-line interface, say so prominently in the changelog and in the
README.
