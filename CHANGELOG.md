# Changelog

## Unreleased
- Fixed the startup banner to print the web page URLs (`/register`, `/login`) instead of the JSON API endpoints (`/auth/register`, `/auth/jwt/login`), which return 405 in a browser.
- Generation failures now return actionable error messages to the UI for configuration problems (unknown source, unreachable Ollama server, missing model) instead of a generic "Failed to generate text"; unexpected errors remain generic to avoid leaking internals. The web UI displays the returned message in the suggestion panel.
- Custom environment variables sent with a generation request (e.g. `TALKPIPE_OLLAMA_SERVER_URL`) now take effect: TalkPipe's cached configuration is reloaded around each request that supplies them, and restored afterwards.
- `ALLOW_CUSTOM_ENV_VARS=false` (documented in `.env.example`) is now honored as an alternative to the `--disable-custom-env-vars` CLI flag.
- The AI Source value is normalized (trimmed and lowercased), so `Ollama` works the same as `ollama`; AI Settings placeholders now show the valid values (`openai`, `anthropic`, `ollama`) instead of misleading examples.
- Registration now enforces the 8-character password minimum server-side (previously only the registration page checked it).
- Replaced the stale `admin_users.py` and `create_superuser.py` scripts in the repository root — which crashed on `list`/`info` with an async lazy-loading error — with thin wrappers that delegate to the maintained `writing_assistant.admin_users` / `writing_assistant.create_superuser` modules.
- docker-compose.yml: replaced the hardcoded personal `env_file` (`.env.podman.NOCOMMIT`, not shipped, which made `docker-compose up` fail after the image build) with an optional `.env`, and removed leftover editing comments.
- Migrated startup database initialization from the deprecated `@app.on_event("startup")` hook to a FastAPI lifespan handler, removing the DeprecationWarning printed on every start.
- Documentation fixes: README compose commands now use the real service names (`writing-assistant`, `writing-assistant-dev`); README Quick Start explains `TALKPIPE_OLLAMA_SERVER_URL` for remote Ollama servers and lists valid Source values; new README "Administration" section links ADMIN_GUIDE.md and the container deployment guide and introduces the `writing-assistant-admin` / `writing-assistant-create-superuser` console commands; ADMIN_GUIDE.md now documents the console commands (the previously documented `python admin_users.py` invocations crashed); the container deployment guide uses the real repository URL and the working `TALKPIPE_OLLAMA_SERVER_URL` variable name (plain `OLLAMA_SERVER_URL` has no effect as an environment variable); `.env.example` likewise.
- Generation requests no longer print custom environment variable values (which may contain API keys) to the server console; only variable names are logged at debug level.
- Renamed DOCKER_DEPLOYMENT.md to CONTAINER_DEPLOYMENT.md and made the container documentation Podman-first (Docker remains a fully compatible alternative with the same arguments); folded in Podman-specific notes: rootless port-conflict messages, `podman-compose` building the image before validating container options, the optional-`.env` compose syntax requirement, and reaching host services via `host.containers.internal`.
- Moved the detailed container troubleshooting (Windows notes, browser connectivity) from the README front page into CONTAINER_DEPLOYMENT.md, leaving a compact pre-built-container section so Installation and Quick Start are prominent.
- Container images now report the real package version: the Dockerfile takes an `APP_VERSION` build argument (compose passes `${APP_VERSION:-0.1.0}`; CI computes it with setuptools_scm) instead of hardcoding 0.1.0.

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