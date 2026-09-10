# Changelog

Notable changes to the TalkPipe Writing Assistant. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); entries within a
release are grouped by kind rather than listed in the order they landed.

## Unreleased

### Added

- **`writing-assistant-tui --standalone`** starts the server inside the
  terminal interface's own process instead of connecting to one started
  separately, and stops it when the TUI exits. It is the same server
  `writing-assistant` runs — same database, JWT secret and AI settings from
  the environment — bound to localhost on port 8001 (`--port <n>` or
  `WRITING_ASSISTANT_PORT`), so documents and the saved login are shared
  with a server started by hand, and a browser on the same machine can use
  it while the TUI is up. The server's log goes to `tui_server.log` next
  to the session file, because the terminal belongs to the TUI. Starting
  is refused with a clear message when the port is already in use (drop
  the flag if that is a writing-assistant server, or pick another port),
  and `--standalone` cannot be combined with `--server`. The "could not
  connect" error and the login screen's help now mention the flag.
- **The browser opens on startup** at the server's URL once it accepts
  connections, as the vault already did; `--no-browser` turns that off
  (the container image passes it).
- **Second launch opens the running instance.** Starting
  `writing-assistant` — or clicking the launcher — while it is already
  running opens the browser at the running server instead of failing on
  the busy port, using the new unauthenticated `GET /health` route, which
  reports the application name and version.
- **Free-port fallback.** When port 8001 is held by some other program and
  no `--port` / `WRITING_ASSISTANT_PORT` was given, the server uses the
  next free port in the 8002–8021 range and announces it. An explicit
  port that is taken still fails with the usual error.

### Changed

- The container image starts the server with `--no-browser`.

## 1.1.0 (2026-09-07)

### Added

- **Change email address and password** for the logged-in user, in both
  interfaces. The web UI's Settings dialog gains an **Account** tab
  showing who is signed in, a Change Email form and a Change Password
  form; the terminal interface has **Account** in the File menu (F2) and
  the command palette, one dialog with the email and the new password
  (leave it blank to keep the current one). Both ask for the current
  password, keep the form open with the server's reason when it refuses
  (wrong current password, address already in use, password shorter than
  8 characters or same as before), and leave the session logged in — the
  new email is what you log in with next time. Backed by two new
  authenticated endpoints, `POST /user/change-password` and
  `POST /user/change-email`, that verify the current password before
  applying the change, so a bearer token alone is not enough.
- **Quick-access templates**: a named, reusable set of writing settings
  (style, audience, tone, background context, generation directive, word
  limit) for documents you write repeatedly — an "Email" template, say.
  Templates are stored per user on the server (new `writing_templates`
  table, created automatically on startup) behind three authenticated
  endpoints — `GET /templates/list`, `POST /templates/save` (create, or
  replace by name), `DELETE /templates/delete/{id}` — so the web UI and the
  terminal interface share one list. In the web UI, **Settings → Writing
  Settings** gained a Quick-access Templates section (name field, **Save as
  Template**, and per-template **Apply**/**Delete**), and a **Templates ▾**
  menu in the header starts a new document from a template. In the
  terminal interface the same controls sit at the bottom of the Settings
  Document tab and `F4` opens the template picker (also in the command
  palette as "New from template"). Starting from a template saves the open
  document first when it has a name; a never-saved document gets the
  Save / Discard / Cancel prompt (new in the web UI for this flow) rather
  than being dropped. Blank template fields fall back to the user's saved
  defaults, as blank document fields do; AI source and model are not part
  of a template.

### Changed

- **Saving a document stores its committed settings.** A save (File → Save,
  Save As, auto-save, and the save-before-leaving below) now writes the
  writing settings last kept with the document — by Save to Document, by
  loading it, by a template, or by Save AI Settings — rather than whatever
  is currently typed in the Settings form. Suggestions still use the form
  as it stands, so a setting can be tried before it is kept. Before, filling
  in the form to author a template and then starting a document from that
  template rewrote the previous document's settings on the way out.
  Reverting to a snapshot now also adopts the snapshot's settings as the
  document's, so the next save keeps them.
- The Settings dialog opens at the top of its tab instead of wherever it
  was last scrolled, and the suggestion panel's prompt now points at the
  mode buttons above it.
- The web UI's Save As dialog asks for a **Name** and says the document is
  stored in your library on the server (shared with the terminal
  interface), not for a "filename" with a `.json` extension.
- The API documentation (`/docs`) and `writing_assistant.__version__`
  report the installed package version instead of a hard-coded `0.1.0`.

### Removed

- The fastapi-users `GET`/`PATCH /users/me` routes. Nothing in the web
  UI, the terminal interface or the admin tools used them, and the `PATCH`
  let a bearer token alone set a new password or email without knowing
  the current password. Self-service now goes through the two
  `/user/change-*` endpoints above; the superuser `/users/{id}` routes
  are unchanged. For a token check, use `GET /auth/check`.

### Fixed

- **File → Open, New and Import no longer drop an unsaved document** in the
  web UI. As the Templates menu already did, they save the open document in
  place first when it has a library name, and otherwise — when it has any
  text or title — ask **Save… / Discard / Cancel**; choosing Save… opens
  Save As and continues with the original action once the save succeeds.
  Before, loading another document replaced an unsaved one silently.

### Documentation

- AI Settings and the README now say where the Server URL, API key and
  environment variables are kept — with your account on the server, once
  Save AI Settings is pressed — rather than "in your browser's local
  storage".
- README: the Quick Start's banner and registration steps match the
  application; the web UI's `Ctrl+G` / `Ctrl+U` hotkeys and the
  save-before-leaving behaviour are described; the "Customizing Generation"
  recipe says which files a new mode touches (and that `script.js` needs no
  edit) and that the server must be restarted; the systemd example uses a
  venv path that matches the install steps; `pip install -e '.[dev]'` is
  quoted so it works in zsh; the environment-variable table gains the
  OpenAI/Anthropic key and base-URL variables.

## 1.0.0 (2026-08-29)

### Added

- **Terminal interface**: `writing-assistant-tui` (also
  `python -m writing_assistant.tui`), a Textual application with the same
  features as the web UI, for places without a browser — an SSH session, a
  tmux window, a headless machine. It is a client of the running server's
  REST API (nothing in the web application changed), so it shares accounts,
  documents, snapshots, and per-user settings with the web interface. It
  provides a login/registration screen; an editor with title, blank-line
  sections, and a suggestion panel that follows the cursor; the four
  generation modes (F5–F8) and "Use This Text" (Ctrl+U); a File menu (F2)
  with New, Save/Save As, Open, Delete, snapshots, Import/Export (same JSON
  format as the web UI), Copy to clipboard, and Log out; and Settings (F3)
  with document metadata, AI source/model, Connection fields, and Test
  Connection. The session token lives in
  `~/.writing_assistant/tui_session.json` (mode 600), so relaunching skips
  login and reopens the last document at its saved cursor position;
  `--server`, `--logout`, `WRITING_ASSISTANT_TUI_SERVER`, and
  `WRITING_ASSISTANT_TUI_HOME` are the knobs. New dependencies: `textual`,
  `httpx`. Tests drive the TUI end-to-end against the in-process FastAPI
  app.
- **Test Connection** button in Settings → AI Settings, backed by a new
  authenticated `POST /ai/test-connection` endpoint. It runs a real,
  token-capped probe through the same TalkPipe adapter generation uses —
  for any registered source — and reports whether the source/model is
  reachable, with an actionable, field-aware reason on failure (missing
  API key, unknown source, unreachable server, model not pulled, and
  container-specific `localhost` advice suggesting
  `http://host.containers.internal:11434`). Empty source/model fall back to
  the server defaults, mirroring generation, and a stale result is cleared
  as soon as the Source, Model, Server URL, or API Key field changes.
- **Connection fields** (Server URL and API Key) in Settings → AI
  Settings, as a friendlier alternative to hand-crafting environment
  variables. They apply to whichever AI source is selected and map
  server-side to the variable that source's client actually reads
  (`TALKPIPE_OLLAMA_SERVER_URL` for Ollama;
  `OPENAI_API_KEY`/`OPENAI_BASE_URL` for OpenAI;
  `ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL` for Anthropic). Like custom
  environment variables, they are applied per-request, restored afterwards,
  and gated behind the same `ALLOW_CUSTOM_ENV_VARS` switch; when that
  switch is off, the section's help text says connection settings are
  managed by the server administrator.
- **System clipboard support in the terminal interface**: Ctrl+V pastes
  text copied in other programs — into the editor, the title, and every
  dialog field — via whichever of `wl-paste`, `xclip`, `xsel`, or
  `pbpaste` is installed, and Ctrl+C / File → Copy mirror copied text back
  to the system clipboard. Without a clipboard tool (e.g. over SSH) the
  app's internal clipboard is used, File → Copy says so instead of
  claiming the text reached the system clipboard, and the terminal's own
  paste keys (Ctrl+Shift+V, Shift+Insert, middle-click) keep working.
- Terminal interface: a suggestion requested while another section's is
  still generating is queued and runs next (the panel shows "Queued")
  instead of being silently dropped, and the "Generating…" status belongs
  to the section under the cursor rather than whichever request is
  running; the Open dialog gained a filter field (typing narrows the list
  by name or title, Up/Down move through matches, Enter opens); and the
  unsaved-changes prompt (Quit, Open, New, Import, Revert, Log out) gained
  a **Save** button that saves — asking for a library name if needed — and
  continues, alongside Discard changes and Cancel.
- The web editor restores the last-open document when the page is reloaded
  (tracked per browser via localStorage; cleared on New, Import, or when
  the document is deleted). Previously a reload always presented an empty
  editor.

### Changed

- The AI Source field in Settings → AI Settings is a dropdown (Server
  default / OpenAI / Anthropic / Ollama) instead of free text, so typos
  like `olama` can no longer be entered. "Server default" sends an empty
  source, deferring to the server's TalkPipe configuration; saved values
  outside the valid set fall back to it. The value is also normalized
  (trimmed and lowercased) server-side, the Model placeholder shows
  realistic examples, and the "Unknown source" error remains as a backstop
  for direct API clients and now lists the accepted values.
- Generation and Test Connection failures return actionable messages built
  by a shared classifier (`core/ai_connection.py`) instead of a generic
  "Failed to generate text" or the raw library error. The exception is
  only *classified* — credentials problem, model not found, server
  unreachable, read timeout (distinguished from "connection refused", with
  a suggestion to retry), or unexpected — and the wording is the app's
  own, pointing at the exact field to fix ("double-check the API Key
  entered in AI Settings", "Enter one in the Model field",
  `ollama pull <model>`). Raw exception text, which can carry internal
  hostnames or paths, is never echoed to the client; full tracebacks go to
  the server log. A request with no source/model and no server default
  says exactly what to do in the app instead of surfacing TalkPipe's
  configuration-file message.
- `/generate-text` rejects an unknown generation mode with a 400 that
  lists the known ones (`GENERATION_MODES` in `core/callbacks.py`). It
  used to fall back to another mode's prompt silently, which hid a
  half-finished custom mode behind plausible output.
- Generation prompts for the rewrite, improve, proofread, and default
  modes ask the model for a single bare paragraph — no heading, title, or
  commentary. Some models returned a title line plus several paragraphs,
  and because "Use This Text" replaces the section verbatim and sections
  split at blank lines, one section became three. Only each prompt's
  closing instruction changed (the `ideas` mode is unaffected); applies to
  both interfaces, which share the endpoint.
- Document and snapshot timestamps in the API (`modified`/`created` in
  `GET /documents/list` and `GET /documents/snapshots/{filename}`) carry
  an explicit `+00:00` offset. Bare UTC values were parsed by browsers as
  *local* time, so the web UI's Open and Revert lists showed the wrong
  wall-clock time. Storage is unchanged (still UTC; no migration), the
  deprecated `datetime.utcnow` is gone, and a snapshot's name and stored
  time are derived from one instant so they always agree.
- Custom environment variables sent with a generation request (e.g.
  `TALKPIPE_OLLAMA_SERVER_URL`) now take effect — TalkPipe's cached
  configuration is reloaded around the request and restored afterwards.
  Their values are no longer printed to the server console (only names,
  at debug level), and `ALLOW_CUSTOM_ENV_VARS=false` is honored as an
  alternative to the `--disable-custom-env-vars` flag.
- Registration enforces the 8-character password minimum server-side
  (previously only the registration page checked it). The login and
  registration pages show human-readable messages instead of raw codes
  (`LOGIN_BAD_CREDENTIALS`, `REGISTER_USER_ALREADY_EXISTS`), and validate
  a stored token with `/auth/check` before auto-redirecting, clearing it
  if stale — a stale token used to bounce visitors from `/register`
  straight back to the editor, making the page appear broken.
- Server startup: the banner prints the web page URLs (`/register`,
  `/login`) rather than the JSON API endpoints (which return 405 in a
  browser); when bound to all interfaces it uses the machine's host name
  instead of the unusable `http://0.0.0.0:<port>/`; it points at
  `writing-assistant-tui`; and it notes when custom environment variables
  are disabled. Starting on a port already in use fails immediately with a
  clear error and a `--port` hint instead of printing the success banner
  first (the check probes every address the host resolves to).
  `writing-assistant-create-superuser` builds its "login at" hint from
  `WRITING_ASSISTANT_HOST`/`WRITING_ASSISTANT_PORT` instead of always
  printing `http://localhost:8001/login`.
- Startup database initialization migrated from the deprecated
  `@app.on_event("startup")` hook to a FastAPI lifespan handler, removing
  the DeprecationWarning printed on every start.
- The stale `admin_users.py` and `create_superuser.py` scripts in the
  repository root — which crashed on `list`/`info` — were replaced with
  thin wrappers around the maintained `writing_assistant.admin_users` /
  `writing_assistant.create_superuser` modules.

### Fixed

Terminal-interface fixes from four rounds of first-use review, driven over
a pty (SSH/tmux) at several terminal sizes:

- Small terminals: the Settings dialog, File menu, and Open/Revert pickers
  scroll instead of being clipped (at 60x16 the File menu's last entries
  were invisible while the highlight kept moving into them, so Enter could
  run "Log out" sight unseen); the login, New Document, and Help dialogs
  fit in 24 rows with their buttons on screen; dialogs never exceed the
  terminal width and their captions wrap; the editor gets the larger share
  of the height (nine rows of text at 80x24 instead of four); the mode
  buttons are hidden below 22 rows so the suggestion panel stays visible,
  switch to short labels below 90 columns so the row is not clipped, and a
  terminal smaller than 60x16 gets a notice saying so; the Settings
  Document tab's buttons fit in 70 columns.
- Focus and keys: Tab moves focus out of the editor to the suggestion
  panel and buttons (it inserted a tab character before); **Create an
  account** and **Back to login** move focus into the form instead of
  leaving it on the toggled button, where a second Enter flipped the mode
  back; Enter in the New Document title submits it; F1 help works on the
  login screen too; **F3** switches between the Settings tabs (Tab cycled
  through the fields without reaching the tab bar) and no longer stops on
  an invisible scroll container; the F5–F8 bindings are derived from the
  same `GENERATION_MODES` list as the mode buttons, so adding a mode gives
  it a working key.
- False "unsaved changes": opening, reopening, reverting, or importing a
  document no longer marks it modified straight away, and neither does
  Save AI Settings on an empty, never-saved document — so Quit, Open, and
  Log out no longer ask to discard changes that were never made.
- **Save AI Settings** applies the chosen source/model to the open
  document as well (as the web client does) instead of silently keeping
  the document's previous model. **Save As** onto an existing library
  name and **File → Export** onto an existing file ask before
  overwriting.
- **Use This Text** with a multi-paragraph suggestion leaves the cursor on
  the first inserted section (it was on the last) and says how many
  sections went in; using an Ideas suggestion — advice, not replacement
  text — asks first.
- Error handling: a Server URL that points at some other HTTP service no
  longer dumps that service's entire HTML error page into the error line —
  the client summarizes it and caps any non-JSON body to a short snippet;
  AI Settings rejects a Server URL without an `http(s)://` scheme at save
  time rather than at the next Test Connection; a failed suggestion is
  shown once, in the panel, not also as a toast over the mode buttons; a
  lingering "could not connect" error is cleared by the next successful
  save; Test Connection against a server older than 1.0.0b1 (no
  `/ai/test-connection` route) explains that the server needs upgrading
  instead of showing a bare "Not Found"; validation errors drop the
  `body.` request prefix.
- Document and snapshot times in the Open and Revert pickers are shown in
  local time (the server stamps them in UTC, which the pickers showed
  as-is, contradicting the local-time stamp in snapshot names).
- The command palette (Ctrl+P) lists the app's own commands — File menu,
  Settings, Help, Use suggestion, and the generation modes — and no longer
  offers Textual's Theme, Maximize, and Screenshot entries.
- Notifications: toasts are cleared when Settings opens so they don't
  cover its buttons; Test Connection reports once, in the dialog's status
  line next to its buttons (not off-screen at the bottom of the form, and
  not also as a toast); Save as Default reports once that it also applied
  to the open document; deleting the open document says its text stays in
  the editor as a way back; progress indicators use plain text instead of
  the ⏳ emoji, whose width breaks layout in some terminals; a first-run
  notification points at F3 → AI Settings when no source/model is
  configured, without implying a choice is required when the server
  provides a default.
- Less work per keystroke on long documents: the cursor offset is read
  from the editor's document instead of re-splitting the whole text on
  every cursor move, and the suggestion panel is only redrawn when the
  section under the cursor (or its state) actually changes.
- Smaller polish: the footer shows Ctrl+Q and F1 on the login screen; the
  create-account form states the 8-character password minimum up front;
  the New Document dialog's button reads "Start Document" and says the
  document is stored in the library on the next Ctrl+S; the Save As
  caption explains why library names end in `.json`; and `--help`
  documents the server-URL precedence, the session file, and that
  `--logout` starts at the login screen.

Web and build fixes:

- Fixed the settings dialog's Environment Variables section lookup, which
  keyed off the first `.settings-section h4` in the document and broke
  when the Connection section was added.
- docker-compose.yml: replaced the hardcoded personal `env_file`
  (`.env.podman.NOCOMMIT`, not shipped, which made `docker-compose up`
  fail) with an optional `.env`, and removed leftover editing comments.
- Fixed the black configuration in pyproject.toml (doubled backslashes in
  the `include`/`extend-exclude` patterns made `black --check` match no
  files and pass vacuously) and reformatted the codebase.
- Tests: `test_main_disable_custom_env_vars` no longer permanently flips
  the module-level `ALLOW_CUSTOM_ENV_VARS` flag, which had made later
  tests order-dependent.

### Security

- Error messages sent to clients never echo raw exception text, which can
  carry internal hostnames, paths, or SDK internals (code scanning
  alert 117) — see the shared error classifier under Changed.
- The terminal interface's clipboard bridge runs the clipboard tool from
  the absolute path `shutil.which` resolved (not a bare name looked up on
  `PATH` again at launch) with `shell=False` explicit. The Bandit
  advisories on that module (B404/B603) were reviewed — the command line
  is a fixed allow-list and clipboard text reaches the tool via stdin only
  — and are annotated on the specific lines, so new subprocess use
  elsewhere in `src/` is still reported.
- The runtime container image no longer ships pip: it was only used to
  install the application wheel, and pip ≥ 25's vendored SBOM made Trivy
  report packages that are not actually installed (setuptools
  CVE-2025-47273, msgpack). A local Trivy scan of the rebuilt image
  reports zero Python findings.
- CI venvs are created with `python -m venv --upgrade-deps` and the seeded
  pip/setuptools are upgraded before the project is installed, clearing a
  Safety failure on the interpreter's bundled setuptools
  (CVE-2026-59890); the build backend now requires `setuptools>=83` so
  source builds never run a vulnerable one either.
- Upgraded the locked `nltk` to 3.10.0 to clear CVE-2026-54293 (pulled in
  as a dependency of safety itself).

### Documentation

- README: Installation says Python 3.11.4+ and walks through creating a
  virtual environment first; Quick Start matches the actual UI (the old
  text referenced buttons that no longer exist); a new Administration
  section links ADMIN_GUIDE.md and the container guide and introduces the
  `writing-assistant-admin` / `writing-assistant-create-superuser`
  commands; compose commands use the real service names.
- README: "Customizing Generation" points at `core/callbacks.py` and
  explains that a new mode also needs its button added to the web UI
  templates and its name registered in `GENERATION_MODES`; provider
  wording is source-neutral (OpenAI, Anthropic, or Ollama — including
  OpenAI-compatible local servers such as LM Studio or vLLM) rather than
  Ollama-centric.
- README: remote-Ollama instructions note that a running server must be
  restarted for `TALKPIPE_OLLAMA_SERVER_URL` to take effect (or set it
  per-user in AI Settings, no restart needed), how to find the model
  names an Ollama server offers (`ollama list` or `/api/tags`), and where
  the TUI takes a remote Ollama address.
- README terminal-interface docs: how to reach AI Settings (F3) and run
  Test Connection before the first suggestion; a key table covering the
  generation keys, Ctrl+N / Ctrl+O, Tab/Shift+Tab, section-editing keys
  (Shift+Arrows, Ctrl+X, Ctrl+Z / Ctrl+Y), and that Ctrl+G also runs
  Ideas; that Save stores the document in the server library while Export
  writes a file; clipboard behavior (Ctrl+C / Ctrl+V always work in-app;
  only the system-clipboard bridge needs a clipboard tool); `--server`
  for non-default ports; `WRITING_ASSISTANT_TUI_SERVER` /
  `WRITING_ASSISTANT_TUI_HOME` in the environment-variable table; and how
  to keep the server running for a terminal-only setup (a tmux one-liner
  and a systemd user unit). The feature list no longer calls snapshots
  "automatic" — they are created on demand and the 10 most recent are
  kept. The in-app F1 help likewise lists the dialog keys and notes that
  a multi-paragraph suggestion becomes several sections when used.
- Documented the **server-wide default AI source and model**
  (`TALKPIPE_DEFAULT_MODEL_SOURCE` / `TALKPIPE_DEFAULT_MODEL_NAME`, or
  the equivalent `~/.talkpipe.toml` keys) in the README, ADMIN_GUIDE
  (new "Server-Wide AI Defaults" section), and CONTAINER_DEPLOYMENT — the
  "Server default" option pointed at a setting described nowhere.
- CONTAINER_DEPLOYMENT.md (renamed from DOCKER_DEPLOYMENT.md; Podman-first,
  with Docker as a fully compatible alternative): new "Connecting the
  Container to an LLM" section (cloud keys, Ollama on the host,
  `OPENAI_BASE_URL`/`ANTHROPIC_BASE_URL`, binding Ollama to a non-loopback
  address); the standalone `podman run` examples include
  `--add-host=host.containers.internal:host-gateway`; removed `-it` from
  `podman-compose exec` examples (the flag is rejected, so every
  documented admin command failed verbatim); backup/restore examples use
  the real compose-created volume name (the unprefixed name silently
  backed up a new empty volume); the `.env` heredoc no longer puts
  comments on value lines or sets a bogus `OPENAI_API_KEY`; noted that
  the development container lacks the console scripts on `PATH` (use
  `python -m …`), that images published before the Connection/Test
  Connection features will not show them, and Podman-specific behavior
  (rootless port conflicts, `host.containers.internal`). The detailed
  container troubleshooting moved here from the README front page.
- ADMIN_GUIDE.md documents the console commands (the previously documented
  `python admin_users.py` invocations crashed); `.env.example` lists
  `ANTHROPIC_API_KEY` alongside `OPENAI_API_KEY` and uses the working
  `TALKPIPE_OLLAMA_SERVER_URL` variable name.

### Build and CI

- Dependencies: talkpipe floor raised from 0.11.1a1 to 1.0.0b2, the first
  release with a `py.typed` marker and typed decorators; the
  `ignore_missing_imports` override for `talkpipe.*` was removed, so mypy
  now checks talkpipe's real types at the call sites. Locked dependencies
  refreshed.
- Dockerfile: the builder stage no longer runs the test suite during image
  builds (it added minutes to every build and its result was ignored);
  images report the real package version via an `APP_VERSION` build
  argument (compose passes `${APP_VERSION:-0.1.0}`; CI computes it with
  setuptools_scm) instead of hardcoding 0.1.0.
- CI: the Safety scan step used `--output` with a filename, which
  safety 3.x rejects, so `safety-report.json` was never generated for the
  artifact upload; it now uses `--save-json`.

## 0.1.4

- README: prominent section on pulling and running the pre-built GHCR
  container with Docker or Podman — optional `pull` (`run` fetches the
  image), Windows one-liners, correct `-v` syntax (`/app/data`), a note
  that public packages need no registry login, the optional
  `WRITING_ASSISTANT_SECRET` omitted from the example, and browser
  connectivity troubleshooting (curl, `127.0.0.1` bind, alternate port,
  Podman on Windows, firewall).
- CI/CD: Docker tags — `latest` only for stable (non-prerelease) GitHub
  releases; `experimental` for pushes to `develop` and for prereleases
  (replaces tag-name substring checks).
- Declared `starlette>=1.0.0` and raised `fastapi[standard]` to
  `>=0.133.0` so installs match the
  `Jinja2Templates.TemplateResponse(request, name, …)` API (Starlette 1.0
  removed the legacy signature).
- Fixed the HTML page routes (`/`, `/login`, `/register`) to use
  Starlette's new `TemplateResponse` argument order, restoring template
  loading (avoids `TypeError: unhashable type: 'dict'`).
- Added `uv.lock` and documented `uv sync` / `uv lock` for reproducible
  dev installs; CI installs with `uv sync --frozen` and
  [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv).
- CI/CD: multi-architecture container builds (linux/amd64, linux/arm64)
  via QEMU on release; single-arch for branch/PR builds for faster
  feedback.
- Documentation: renamed `OLLAMA_BASE_URL` to `OLLAMA_SERVER_URL` in the
  README, DOCKER_DEPLOYMENT.md, and `.env.example`.

## 0.1.3

- Made the AI generation mode buttons smaller and arranged them in a
  single row for better visibility on small screens.
- Fixed a progressive slowdown during extended editing sessions: removed
  34 debug `console.log` statements that fired on every keystroke
  (including logs of the full document text), keeping only one-time
  initialization logs.
- Optimized section parsing for smoother typing: 150 ms debounce on
  `parseSections`, a length pre-filter before Levenshtein distance
  calculations, and index-based matching that checks same-position
  sections first. Suggestions no longer flicker during typing, the keyup
  handler only triggers cursor updates for navigation keys, and the mode
  and "Use suggestion" buttons no longer steal focus from the editor.
- Fixed async issues that caused the unit tests and the admin command to
  hang.

## 0.1.2

- Enhanced AI context generation to include multiple paragraphs (up to
  2000 characters each way) instead of just the adjacent ones: the
  frontend collects context from several preceding and following
  sections, and the backend truncates it (last 2000 characters of
  previous context, first 2000 of next). Added tests for truncation and
  multi-paragraph collection.
- Redesigned the AI generation UI: removed the separate "Generate"
  button and replaced the radio buttons with large, descriptive icon
  buttons (Ideas 💡, Rewrite ✏️, Improve ✨, Proofread 🔍) with hover
  tooltips — a click triggers generation immediately, with a pulsing
  indicator while it runs.
- Fixed dark mode styling: replaced hard-coded light backgrounds with CSS
  variables (loading indicators, dropdowns, form inputs, sections, and
  containers), improved contrast and border visibility, and fixed light
  mode to use a light gradient — the background now changes properly when
  toggling modes.
- Adjusted the generation prompt to make clear which text is context and
  which is the target paragraph.

## 0.1.1

- Addressed an "information exposure through exception" issue.
- Specified Python 3.11.4 or higher to mitigate CVE-2025-8869 (pip
  symbolic-link path traversal): Python ≥ 3.11.4 implements PEP 706 safe
  tar extraction, significantly reducing the attack surface (a full fix
  requires pip 25.3+).
- Migrated the Docker base image from `python:3.13-slim` (Debian) to
  `fedora:latest`: eliminates OpenSSH and Perl `File::Temp`
  vulnerabilities flagged in the Debian base, reduces the attack surface,
  and matches the TalkPipe project's architecture.

## 0.1.0

- Improved working version with multi-user accounts.

## 0.0.1

- Basic working version using Jupyter-notebook-like tokens.

---
Last Reviewed: 20260829
