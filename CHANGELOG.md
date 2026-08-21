# Changelog

## Unreleased
- CI: every job's project venv is now created with `python -m venv --upgrade-deps`. On Python 3.11 a fresh venv seeds setuptools from the interpreter's bundled wheel (79.0.1 on the CI runners); nothing in the project depends on setuptools at runtime, but that copy sits in the scanned environment and the Safety dependency scan failed on it (CVE-2026-59890, fixed in setuptools 83.0.0). The seeded pip and setuptools are now upgraded to current releases before the project is installed — the previous step only upgraded pip. The build backend's requirement is also raised to `setuptools>=83` so builds from source never run a vulnerable setuptools either.
- Dependencies: talkpipe floor raised from 0.11.1a1 to 1.0.0b2, the first release that ships a `py.typed` marker and typed `@segment`/`@source` decorators. mypy no longer treats `talkpipe.*` as a missing-import module (the `ignore_missing_imports` override for it was removed), so talkpipe's real types are now checked at the call sites, and `disallow_untyped_decorators` remains enabled with no errors. Locked dependencies refreshed accordingly.
- Dockerfile: the runtime image no longer ships pip. It was only used to install the application wheel, and pip ≥ 25 bundles an SBOM of its own vendored code (`pip/_vendor/bom.cdx.json`) that Trivy reported as installed packages — the GitHub Security tab flagged setuptools 70.3.0 (CVE-2025-47273, HIGH) and msgpack 1.1.2 even though neither is actually installed in the image. pip is now removed (`dnf remove python3-pip`) after the wheel is installed; a local Trivy scan of the rebuilt image reports zero Python findings.
- README and CONTAINER_DEPLOYMENT.md no longer read as Ollama-centric: provider wording now says the app works with LLM endpoints including OpenAI, Anthropic, or Ollama — Ollama-first phrasings were reordered, and the Connection-fields and "Customizing Generation" notes were reframed to be source-neutral.
- New **Test Connection** button in Settings → AI Settings (modeled on the TalkPipe workbench settings dialog): a new authenticated `POST /ai/test-connection` endpoint runs a real, token-capped probe through the same TalkPipe adapter generation uses — for any registered source (openai, anthropic, ollama, ...) — and reports whether the source/model is reachable, with an actionable reason on failure (missing key, unknown source, unreachable server, model not pulled). Empty source/model fall back to the server defaults, mirroring generation. When Ollama is unreachable at a localhost URL, the message explains that inside a container "localhost" is the container itself and suggests `http://host.containers.internal:11434`. Failure hints are field-aware: when the failing Server URL or API Key was entered in the dialog itself, the message says to double-check that field (instead of steering the user toward server-side environment variables they were not using), and a missing cloud key points at the API Key field right above the button as the one-click fix alongside the server-side variable. A stale test result no longer lingers: the status is cleared as soon as the Source, Model, Server URL, or API Key field changes (a previous "✓ Connected" only vouched for the values it was run with). Failure reasons never echo the raw exception text (which can carry internal hostnames, paths, or SDK internals — code scanning alert 117): the exception is only *classified* — credentials problem, model not found on the server, server unreachable, or unexpected — and the message for that category is written by the app from safe inputs (source, model name, and for unexpected errors the exception class name plus a pointer to the server log, where the full traceback is recorded). A missing Ollama model now suggests `ollama pull <model>` rather than the container/URL advice, which only applies when the server itself is unreachable.
- New source-aware **Connection** fields in Settings → AI Settings — **Server URL** and **API Key** — as a friendlier alternative to hand-crafting environment variables. They apply to whichever AI source is selected and map server-side to the variable that source's client actually reads (`TALKPIPE_OLLAMA_SERVER_URL` for Ollama; `OPENAI_API_KEY`/`OPENAI_BASE_URL` for OpenAI; `ANTHROPIC_API_KEY`/`ANTHROPIC_BASE_URL` for Anthropic). Applied per-request and restored afterwards, like custom environment variables, and gated behind the same `ALLOW_CUSTOM_ENV_VARS` switch (the raw environment-variables editor remains for anything else). Fixed the settings dialog's Environment Variables section lookup to survive the new section (it previously keyed off the first `.settings-section h4` in the document). When the server disables custom environment variables, the Connection section's help text now explains that connection settings are managed by the server administrator instead of keeping the default "Leave blank to use the server's configuration" wording, which referred to input fields that are hidden in that mode.
- `writing-assistant-create-superuser` now builds its closing "You can now login at:" hint from `WRITING_ASSISTANT_HOST`/`WRITING_ASSISTANT_PORT` (the same variables and defaults the server uses) instead of always printing `http://localhost:8001/login`.
- README "Customizing Generation" now explains that adding a new generation mode also requires adding its button to the web UI (`app/templates/index.html` / `app/static/script.js`) — the previous wording implied editing `core/callbacks.py` alone was enough, but the mode buttons are defined in the templates.
- CONTAINER_DEPLOYMENT.md: noted that the Connection section / Test Connection button are recent additions, so images published before the feature (including older `latest` tags) will not show them — pull a newer tag or build from source.
- CONTAINER_DEPLOYMENT.md: new "Connecting the Container to an LLM" section covering cloud keys (server-wide via `-e`/`.env` or per-user via the UI) and the Ollama-on-the-host case; the standalone `podman run` examples now include `--add-host=host.containers.internal:host-gateway` (previously only compose mapped the host gateway, so the documented GHCR run could not reach an Ollama server on the host); documented `OPENAI_BASE_URL`/`ANTHROPIC_BASE_URL` and the need to bind Ollama to a non-loopback address (`OLLAMA_HOST=0.0.0.0`); new troubleshooting entry pointing at Test Connection. `.env.example` updated to match.
- CI: the Safety dependency scan step passed a filename to `--output`, which safety 3.x rejects (it expects a format like `json`), so `safety-report.json` was never generated for the artifact upload; it now uses `--save-json`. Also upgraded the locked `nltk` from 3.9.4 to 3.10.0 to clear CVE-2026-54293 (a path-traversal advisory in nltk, pulled in as a dependency of safety itself), which was failing the `safety check` gate in CI.
- When a generation request has no AI source/model and the server has no default, the error now tells the user exactly what to do in the app ("Open Settings → AI Settings and choose an AI Source / enter a Model name", distinguishing a missing model from a missing source) instead of surfacing the library's "specified in the configuration file, or in environment variables" message, which means nothing to a web-UI user.
- The login page now shows "Incorrect email or password." instead of the raw `LOGIN_BAD_CREDENTIALS` code; the registration page likewise maps `REGISTER_USER_ALREADY_EXISTS` (in both string and object forms) and displays the human-readable reason for password-validation failures.
- The login and register pages validate a stored token with `/auth/check` before auto-redirecting, and clear it if it is stale (e.g. after a database reset). Previously a stale token bounced visitors from `/register` or `/login` to the editor and straight back, making the register page appear broken.
- Starting the server on a port that is already in use now fails immediately with a clear error and a `--port` hint, instead of printing the full success banner (URLs, database path) before uvicorn's bind error. The check probes every address the host resolves to, so a conflict on 127.0.0.1 is caught even on systems where `localhost` resolves to `::1` first. The server startup tests also no longer depend on the default port 8001 being free on the machine running the test suite (they previously failed if another instance of the app was running).
- CONTAINER_DEPLOYMENT.md: documented that the development container (`writing-assistant-dev`) does not have the console scripts on `PATH` — use `python -m writing_assistant.admin_users` / `python -m writing_assistant.create_superuser` there.
- README: new "Customizing Generation" note pointing at `core/callbacks.py` (prompt templates and generation modes) and explaining that any Ollama/OpenAI/Anthropic-compatible endpoint can be used.
- The editor now restores the last-open document when the page is reloaded or reopened (tracked per browser via localStorage; cleared on New, Import, or when the document is deleted). Previously a reload always presented an empty editor and the previous document had to be re-opened via File → Open.
- The "Unknown source" generation error now lists the accepted values (`openai`, `anthropic`, `ollama`) instead of only naming the rejected one.
- The AI Source field in Settings → AI Settings is now a dropdown (Server default / OpenAI / Anthropic / Ollama) instead of a free-text input, so typos like `olama` can no longer be entered. "Server default" (the initial selection) sends an empty source, deferring to the server's TalkPipe configuration — the same behavior as the previous empty field. Saved or per-document source values outside the valid set fall back to Server default; the server-side "Unknown source" error remains as a backstop for direct API clients.
- Dockerfile: the builder stage no longer runs the test suite during image builds — it added minutes to every `podman-compose up`/`podman build` and its result was ignored (`|| true`). Tests run in CI.
- Documentation fixes from an onboarding review:
  - README Installation now says Python 3.11.4+ (matching `requires-python`) and explains creating a virtual environment first, since `pip install` fails or is blocked on the system Python of most modern distros.
  - README Quick Start step 4 was rewritten to match the actual UI (the editor opens directly after login; generation via the Ideas/Rewrite/Improve/Proofread buttons and "← Use This Text"; saving via File → Save) — the previous text referenced "Create New Document", "Generate", and "Save Document" buttons that no longer exist. Step 2 now says "Create Account" (the register button's real label).
  - README remote-Ollama instructions note that an already-running server must be restarted for `TALKPIPE_OLLAMA_SERVER_URL` to take effect, and document the alternative of setting it per-user under Settings → AI Settings → Environment Variables (no restart needed).
  - CONTAINER_DEPLOYMENT.md: removed `-it` from all `podman-compose exec` examples — podman-compose rejects the flag (`error: unrecognized arguments: -it`), so every documented interactive admin command failed verbatim; `exec` is interactive by default.
  - CONTAINER_DEPLOYMENT.md: backup, restore, and volume-removal examples now use the real compose-created volume name (`talkpipe-writing-assistant_writing_assistant_db`) and tell readers to confirm it with `podman volume ls`. The previous examples used the unprefixed name, which silently creates a new empty volume — the documented backup backed up nothing.
  - CONTAINER_DEPLOYMENT.md: the `.env` heredoc example no longer puts a comment on the same line as a value (inline `#` becomes part of the value in .env files) and no longer sets a bogus placeholder `OPENAI_API_KEY`.
  - `ANTHROPIC_API_KEY` is now listed alongside `OPENAI_API_KEY` in `.env.example` and the container guide's optional variables (Anthropic is a fully supported backend but had no documented variable).
- Fixed the startup banner to print the web page URLs (`/register`, `/login`) instead of the JSON API endpoints (`/auth/register`, `/auth/jwt/login`), which return 405 in a browser.
- Generation failures now return actionable error messages to the UI for configuration problems (unknown source, unreachable Ollama server, missing model, and missing OpenAI/Anthropic API keys) instead of a generic "Failed to generate text"; unexpected errors remain generic to avoid leaking internals. The web UI displays the returned message in the suggestion panel. These messages are now built the same way as the Test Connection button's (shared classifier in `core/ai_connection.py`): the exception is only classified — credentials, model not found, server unreachable, or an unrelated `ValueError` — and the wording is the app's own, using the request's source/model and pointing at the Server URL / API Key fields when those were in play ("double-check the API Key entered in AI Settings", `ollama pull <model>`, container `localhost` advice), instead of echoing the library/SDK exception text (which can carry internal hostnames or paths — same class of issue as code scanning alert 117).
- Custom environment variables sent with a generation request (e.g. `TALKPIPE_OLLAMA_SERVER_URL`) now take effect: TalkPipe's cached configuration is reloaded around each request that supplies them, and restored afterwards.
- `ALLOW_CUSTOM_ENV_VARS=false` (documented in `.env.example`) is now honored as an alternative to the `--disable-custom-env-vars` CLI flag.
- The AI Source value is normalized (trimmed and lowercased), so `Ollama` works the same as `ollama`; the Model placeholder now shows realistic examples instead of misleading ones.
- Registration now enforces the 8-character password minimum server-side (previously only the registration page checked it).
- Replaced the stale `admin_users.py` and `create_superuser.py` scripts in the repository root — which crashed on `list`/`info` with an async lazy-loading error — with thin wrappers that delegate to the maintained `writing_assistant.admin_users` / `writing_assistant.create_superuser` modules.
- docker-compose.yml: replaced the hardcoded personal `env_file` (`.env.podman.NOCOMMIT`, not shipped, which made `docker-compose up` fail after the image build) with an optional `.env`, and removed leftover editing comments.
- Migrated startup database initialization from the deprecated `@app.on_event("startup")` hook to a FastAPI lifespan handler, removing the DeprecationWarning printed on every start.
- Documentation fixes: README compose commands now use the real service names (`writing-assistant`, `writing-assistant-dev`); README Quick Start explains `TALKPIPE_OLLAMA_SERVER_URL` for remote Ollama servers and lists valid Source values; new README "Administration" section links ADMIN_GUIDE.md and the container deployment guide and introduces the `writing-assistant-admin` / `writing-assistant-create-superuser` console commands; ADMIN_GUIDE.md now documents the console commands (the previously documented `python admin_users.py` invocations crashed); the container deployment guide uses the real repository URL and the working `TALKPIPE_OLLAMA_SERVER_URL` variable name (plain `OLLAMA_SERVER_URL` has no effect as an environment variable); `.env.example` likewise.
- Generation requests no longer print custom environment variable values (which may contain API keys) to the server console; only variable names are logged at debug level.
- Renamed DOCKER_DEPLOYMENT.md to CONTAINER_DEPLOYMENT.md and made the container documentation Podman-first (Docker remains a fully compatible alternative with the same arguments); folded in Podman-specific notes: rootless port-conflict messages, `podman-compose` building the image before validating container options, the optional-`.env` compose syntax requirement, and reaching host services via `host.containers.internal`.
- Moved the detailed container troubleshooting (Windows notes, browser connectivity) from the README front page into CONTAINER_DEPLOYMENT.md, leaving a compact pre-built-container section so Installation and Quick Start are prominent.
- Container images now report the real package version: the Dockerfile takes an `APP_VERSION` build argument (compose passes `${APP_VERSION:-0.1.0}`; CI computes it with setuptools_scm) instead of hardcoding 0.1.0.
- Fixed the black configuration in pyproject.toml (the `include`/`extend-exclude` patterns contained doubled backslashes, so `black --check` matched no files and passed vacuously) and reformatted the codebase so the check is meaningful.

## 0.1.4
- README: Pre-built container section — optional `pull` (`run` fetches the image); avoid `pull pull` typo; Windows `docker`/`podman` one-liners; correct `-v` syntax (`/app/data`); browser connectivity troubleshooting (curl, `127.0.0.1` bind, alternate port, Podman on Windows, firewall).
- README: Pre-built container run example omits optional `WRITING_ASSISTANT_SECRET` (defaults apply).
- README: Prominent section on pulling and running the pre-built GHCR container with Docker or Podman; note that public packages do not require registry login.
- CI/CD: Docker tags — `latest` only for stable (non-prerelease) GitHub releases; `experimental` for pushes to `develop` and for prerelease GitHub releases (replaces tag-name substring checks).
- Declared `starlette>=1.0.0` and raised `fastapi[standard]` minimum to `>=0.133.0` so installs match the `Jinja2Templates.TemplateResponse(request, name, …)` API (Starlette 1.0 removed the legacy `(name, context)` signature).
- Added `uv.lock` and documented `uv sync` / `uv lock` for reproducible dev installs; CI installs with `uv sync --frozen` and [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv).
- Fixed HTML page routes (`/`, `/login`, `/register`) to use Starlette’s `TemplateResponse(request, name, …)` argument order, restoring Jinja2 template loading (avoids `TypeError: unhashable type: 'dict'`).
- CI/CD: Build Docker containers for multiple architectures (linux/amd64, linux/arm64) using QEMU emulation
- CI/CD: Use single-arch (linux/amd64) for branch/PR builds; multi-arch only on release for faster feedback
- Documentation: Renamed `OLLAMA_BASE_URL` to `OLLAMA_SERVER_URL` in README, DOCKER_DEPLOYMENT.md, and .env.example

## 0.1.3
- Made AI generation mode buttons smaller and arranged in a single row for better visibility on small screens
- Fixed potential performance issue causing progressive slowdown during extended editing sessions
  - Removed 34 debug console.log statements that fired on every keystroke
  - Eliminated logging of full document text and section arrays during typing
  - Retained one-time initialization logs for startup troubleshooting
- Optimized section parsing performance for smoother typing experience
  - Added 150ms debounce to parseSections to avoid expensive operations on every keystroke
  - Added length pre-filter to skip Levenshtein distance calculation when strings differ by >2x in length
  - Implemented index-based matching to check same-position sections first before searching all sections
  - Fixed suggestion panel stability: suggestions no longer flicker during typing
  - Keyup handler now only triggers cursor updates for navigation keys (arrows, Home, End, etc.)
  - Mode buttons and "Use suggestion" button no longer steal focus from the editor
- Updated async issues causing unit tests and the admin command to hang.

## 0.1.2
- Enhanced AI context generation to include multiple paragraphs (up to 2000 characters) instead of just adjacent paragraphs
  - Frontend now collects context from multiple preceding and following sections
  - Backend truncates context to 2000 characters (last 2000 for previous context, first 2000 for next context)
  - Provides richer context for AI text generation while managing token usage
  - Added comprehensive tests: truncation with long paragraphs and multi-paragraph collection with short paragraphs
- Redesigned AI generation UI for improved usability
  - Removed separate "Generate" button
  - Replaced radio buttons with large, descriptive icon buttons (Ideas 💡, Rewrite ✏️, Improve ✨, Proofread 🔍)
  - Each button includes hover tooltips explaining its purpose
  - Direct click triggers generation immediately
  - Visual feedback with pulsing indicator during generation
  - Streamlined workflow reduces clicks and improves discoverability
- Fixed dark mode styling issues
  - Replaced hard-coded light backgrounds with CSS variables that adapt to dark mode
  - Fixed loading indicators, dropdowns, form inputs, sections, and containers
  - Dark mode now has consistent dark theming throughout the application
  - Improved text contrast and border visibility in dark mode
  - Fixed light mode background to use proper light gradient (was incorrectly using dark colors)
  - Background now properly changes when toggling between light and dark modes
- Adjusted prompt generation to make it clear what text was context and what was the target paragraph 

## 0.1.1
- Addressed "information exposure through exception" issue
- Specified python 3.11.4 or higher to mitigate CVE-2025-8869 (pip symbolic link path traversal)
  - Python >=3.11.4 implements PEP 706 which provides safe tar extraction
  - Significantly reduces attack surface for this vulnerability
  - Full fix requires pip 25.3+ (not yet released)
- Migrated Docker base image from python:3.13-slim (Debian) to fedora:latest for improved security posture
  - Eliminates OpenSSH vulnerability (null character in ssh:// URI leading to code execution via ProxyCommand)
  - Eliminates Perl File::Temp insecure temporary file handling vulnerabilities
  - Reduces attack surface by using minimal Fedora base without unnecessary packages
  - Maintains consistency with TalkPipe project architecture

## 0.1.0
- Improved working version with multi-user accounts

## 0.0.1
- Basic working version using jupyter notebook-like tokens