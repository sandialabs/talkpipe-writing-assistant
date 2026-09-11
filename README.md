<center><img src="docs/logo.png" width=400></center>

# TalkPipe Writing Assistant

Making the AI write _with_ you, not _for_ you.

An AI-powered writing assistant that transforms how you create structured documents. This application combines intelligent content generation with intuitive document management, enabling writers to craft professional documents with contextually-aware AI assistance that understands your style, audience, and objectives.

Built on the [TalkPipe framework](https://github.com/sandialabs/talkpipe), this tool helps you:

- **Break writer's block**: Generate initial drafts and ideas for any section
- **Maintain consistency**: AI understands your document's context, style, and tone across all sections
- **Iterate quickly**: Multiple generation modes (rewrite, improve, proofread, ideas) let you refine content efficiently
- **Stay organized**: Structure documents into sections with main points and supporting text
- **Use the LLM of your choice**: Works with LLM endpoints including OpenAI, Anthropic, and Ollama — cloud APIs, compatible gateways, or fully local, offline models

<center><img src="docs/screenshot.png" width=80%></center>

## Features

- **Multi-User Support**: JWT-based authentication with per-user document isolation
- **Structured Document Creation**: Organize your writing into sections with main points and user text
- **AI-Powered Generation**: Generate contextually-aware paragraph content using advanced language models
- **Multiple Generation Modes**:
  - **Rewrite**: Complete rewrite with new ideas and improved clarity
  - **Improve**: Polish existing text while maintaining structure
  - **Proofread**: Fix grammar and spelling errors only
  - **Ideas**: Get specific suggestions for enhancement
- **Real-time Editing**: Dynamic web interface for seamless writing and editing
- **Terminal Interface**: `writing-assistant-tui` offers the same features in any terminal — an SSH session, a tmux window, a machine with no browser
- **Document Management**: Save, load, and manage multiple documents, with snapshots you can revert to
- **User Preferences**: Per-user AI settings, writing style, and environment variables
- **Customizable Metadata**: Configure writing style, tone, audience, and generation parameters
- **Quick-access Templates**: Save a set of writing settings under a name (an "Email" template, say) and start a new document from it in one step — from the **Templates ▾** menu in the web UI or `F4` in the terminal interface
- **Flexible AI Backend**: Works with LLM endpoints including OpenAI (GPT-4, GPT-4o), Anthropic (Claude 3.5 Sonnet, Claude 3 Opus), and Ollama (llama3, mistral, etc.) — chosen per account; see [LLM providers](#llm-providers)
- **Database Storage**: SQLite database with configurable location for easy backup and deployment
- **Async Processing**: Efficient queuing system for AI generation requests

## Pre-built container (Podman or Docker)

CI publishes a public image to [GitHub Container Registry](https://github.com/sandialabs/talkpipe-writing-assistant/pkgs/container/talkpipe-writing-assistant) (`ghcr.io/sandialabs/talkpipe-writing-assistant`; Linux amd64/arm64; no registry login needed). Run it with the database persisted under `/app/data`:

```bash
podman run --rm -p 8001:8001 \
  -v wa_data:/app/data \
  ghcr.io/sandialabs/talkpipe-writing-assistant:latest
```

Then open **http://localhost:8001** (use `http`, not `https`). `docker run` works with the same flags. `run` pulls the image automatically — no separate `pull` step is needed.

**Tags:** `latest` — stable release; `experimental` — pre-releases. Images are published only on releases, each also tagged with its version and commit SHA.

For Windows notes, connectivity troubleshooting, building from a local clone,
and production deployment, see the
[Container Deployment Guide](CONTAINER_DEPLOYMENT.md).

## Installation

### Prerequisites

- Python 3.11.4 or higher
- Access to an LLM endpoint — any one of OpenAI, Anthropic, Ollama (local),
  or a compatible endpoint; Ollama is not required (see
  [LLM providers](#llm-providers))

> **Note:** On most modern systems (Debian/Ubuntu, Fedora, macOS with Homebrew),
> installing into the system Python is blocked or `pip` is not installed at all.
> Create a virtual environment first — the `pip` commands below assume one is
> active:
>
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate   # Windows: .venv\Scripts\activate
> ```

### Install from pip (Recommended)

```bash
pip install talkpipe-writing-assistant
```

After installation, you can start the application immediately:

```bash
writing-assistant
```

Your browser opens at `http://localhost:8001` (pass `--no-browser` to skip
that). See the [Quick Start](#quick-start) section below for next steps.

### Install from source

```bash
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd talkpipe-writing-assistant
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd talkpipe-writing-assistant
pip install -e '.[dev]'
```

### Development environment (uv, with a reproducible lock)

The default branch, `stable`, is release-only: it points at the latest
release, so what you see on the repository's front page describes that
release. Development happens on `main`, which is where merge requests go and
where unreleased changes and their documentation accumulate — check it out
first (`git checkout main` after cloning).

The repo includes [`uv.lock`](uv.lock) so contributors share one resolved set of versions. Install [uv](https://github.com/astral-sh/uv), then:

```bash
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd talkpipe-writing-assistant
uv sync --extra dev
```

Run tests and tools via the project environment, for example `uv run pytest`, or activate the virtualenv (`.venv` on Unix: `source .venv/bin/activate`).

**Code quality.** CI fails on any finding from `ruff check .`, `ruff format --check .`, or `mypy` (rule set and type-checking config live in `pyproject.toml`), so run them before pushing — `ruff check --fix . && ruff format .` fixes most findings. To run the same checks on every commit, opt in once per clone with `uv run pre-commit install`; `pre-commit run --all-files` reproduces the CI gate locally.

**CI does not use the lockfile.** It installs with pip (`pip install -e '.[dev]'`) and resolves dependencies fresh, on purpose: that is what someone running `pip install talkpipe-writing-assistant` gets, so the build breaks when *they* would break. A dependency problem that only the lockfile hides is one we want CI to see — this project has been bitten by exactly that, when an unpinned FastAPI release broke it.

Two consequences worth remembering:

- `uv.lock` is a development convenience. It pins nothing for users and is not a security control — the version floors in `pyproject.toml` are what actually protect an install. Fix a vulnerable dependency by raising its floor, not by refreshing the lock.
- The lock must still stay honest. CI runs `uv lock --check`, which installs nothing and fails only when `uv.lock` and `pyproject.toml` have drifted apart. After changing dependencies in `pyproject.toml`, run `uv lock` and commit `uv.lock`. To bump versions, use `uv lock --upgrade` or `uv lock --upgrade-package <name>`.

### Using a container (Podman or Docker)

Build and run from the repository (as opposed to the [pre-built GHCR image](#pre-built-container-podman-or-docker) above):

```bash
# Optional: create a local configuration file first
cp .env.example .env

# Production deployment
podman-compose up writing-assistant

# Development with live reload
podman-compose --profile dev up writing-assistant-dev
```

`docker-compose` (or `docker compose`) works with the same arguments.

See the [Container Deployment Guide](CONTAINER_DEPLOYMENT.md) for the full
deployment guide (configuration, backups, user management, and production
hardening).

## Quick Start

**TL;DR:** After `pip install talkpipe-writing-assistant`, just run `writing-assistant` — it opens `http://localhost:8001` in your browser!

After installing with pip, follow these steps to get started:

### 1. Start the Server

```bash
writing-assistant
```

The server will start on `http://localhost:8001`, open it in your browser,
and display:

```
🔐 Writing Assistant Server - Multi-User Edition
📝 Access your writing assistant at: http://localhost:8001/
🔑 Register a new account at: http://localhost:8001/register
🔐 Login at: http://localhost:8001/login
📚 API documentation: http://localhost:8001/docs
💻 Terminal interface (no browser needed): run `writing-assistant-tui` in another terminal
💾 Database: /home/user/.writing_assistant/writing_assistant.db
🌐 Opening in your web browser...
```

If another program already holds port 8001, the server uses the next free
port and says so; running `writing-assistant` while it is already running
just opens the browser at the running instance.

### 2. Create Your Account

1. Open your browser and navigate to `http://localhost:8001/register`
2. Enter your email address and a password (at least 8 characters, typed twice)
3. Click "Create Account", then log in on the login page

### 3. Configure AI Backend

Pick a model provider. Any one of the three below works — Ollama is not
required, and neither is a cloud account. Whichever you choose is set the
same way, in **Settings → AI Settings** (in the terminal interface: `F3` →
AI Settings). [LLM providers](#llm-providers) is the full reference,
including OpenAI-compatible servers and server-wide defaults.

**Option A: OpenAI (Cloud)**
1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. In AI Settings, set Source to `openai` and Model to your model of choice
   (e.g. `gpt-4o`), and paste the key into **Connection → API Key**.
   Alternatively, set it server-wide: `export OPENAI_API_KEY="sk-your-api-key-here"`
   in the shell you start `writing-assistant` from.

**Option B: Anthropic (Cloud)**
1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. In AI Settings, set Source to `anthropic` and Model to your model of
   choice (e.g. `claude-sonnet-4-5`), and paste the key into **Connection →
   API Key**. Alternatively, set it server-wide:
   `export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"` in the shell you
   start `writing-assistant` from.

**Option C: Ollama (Local, Free)**
1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull [model name]`
3. Start Ollama: `ollama serve`
4. In AI Settings, set Source to `ollama` and Model to [model name]. The name must match one Ollama has pulled: `ollama list` shows them on the Ollama machine, or `curl http://your-ollama-host:11434/api/tags` from anywhere; Test Connection reports a name Ollama does not have.

If Ollama runs on a different machine (or a non-default port), enter its
address in **Connection → Server URL**, or set `TALKPIPE_OLLAMA_SERVER_URL`
before starting the server:

```bash
export TALKPIPE_OLLAMA_SERVER_URL="http://your-ollama-host:11434"
writing-assistant
```

A server-wide variable (an API key or the Ollama address) is read when the
server starts: if it is already running, stop it and start it again with
the variable set. The Connection fields need no restart.

Whichever option you picked, press **Test Connection** — it makes a real
round trip and reports exactly what is wrong (missing key, unreachable
server, model not pulled) — then **Save AI Settings**. The settings are
saved with your account on the server, so the terminal interface uses them
too.

### 4. Start Writing!

1. After logging in, the editor opens directly — add a title and start typing.
   Leave a blank line between sections (paragraphs).
2. Place your cursor in a section, then click one of the generation buttons
   below the editor — **Ideas**, **Rewrite**, **Improve**, or **Proofread** —
   to create AI-assisted content for that section (`Ctrl+G` runs Ideas from
   the keyboard).
3. When you like a suggestion, click **"← Use This Text"** (or press
   `Ctrl+U`) to replace the section with it. Both keys can be changed under
   Settings → AI Settings → Hotkeys.
4. Save your work via the **File ▾** menu (**File → Save**); the first save
   asks for a name in your library on the server (shared with the terminal
   interface — use File → Export for a file). The File menu also offers Save
   As, Open, snapshots, and import/export. Open, New and Import save the
   current document first when it has a name; a document that was never
   saved gets a **Save… / Discard / Cancel** prompt instead.
5. **Settings → Writing Settings** holds the style, audience, tone, context,
   directive, and word limit that shape every suggestion. Suggestions use
   whatever is in the form, so you can try a setting straight away; **Save
   to Document** is what stores it with this document, and **Save as
   Default** makes the form the starting point for new ones.

That's it! You're ready to use the AI writing assistant.

### Quick-access templates

For writing you do again and again — emails, status updates, cover letters
— save the writing settings once as a **template** and reuse them:

1. Open **Settings → Writing Settings**, fill in the fields (a short
   directive such as "Three short paragraphs; end with a clear ask" is the
   useful part), enter a name under **Quick-access Templates**, and press
   **Save as Template**. Saving under an existing name replaces that
   template; **Apply** fills the form from one, and **Delete** removes it.
2. Choose the template from the **Templates ▾** menu in the header. This
   starts a new, empty document with the template's settings. The document
   you were working on is saved first when it has a name; a document that
   was never saved gets a **Save… / Discard / Cancel** prompt instead.
   Authoring a template does not change the open document — only **Save to
   Document** does.

Templates are stored with your account, so the terminal interface sees
the same list (`F4` there). A blank template field falls back to your
saved default, as a blank document field does; AI source and model are
not part of a template — they come from your defaults.

## LLM providers

The writing assistant is not tied to Ollama, or to any one provider. It
generates text through TalkPipe, and **AI Settings** (Settings → AI Settings
in the web interface, `F3` → AI Settings in the terminal interface) offers
these sources. Their client libraries are installed with the application, so
nothing extra is needed on the server beyond access to the model service.

| AI Source | What it talks to | Credentials | Endpoint (default → override) |
|-----------|------------------|-------------|-------------------------------|
| `openai` | OpenAI's API, or any OpenAI-compatible server (LM Studio, vLLM, llama.cpp's server, a corporate gateway) | **API Key** field, or `OPENAI_API_KEY` | OpenAI's API → **Server URL** field, or `OPENAI_BASE_URL` |
| `anthropic` | Anthropic's API, or an Anthropic-compatible gateway | **API Key** field, or `ANTHROPIC_API_KEY` | Anthropic's API → **Server URL** field, or `ANTHROPIC_BASE_URL` |
| `ollama` | An Ollama server on this machine or another — free, and can run fully offline | none | `http://localhost:11434` → **Server URL** field, or `TALKPIPE_OLLAMA_SERVER_URL` |
| Server default | Whichever source the administrator configured — see [Server default](#server-default-administrators) | as for that source | as for that source |

**Model** is the model's name on that service — e.g. `gpt-4o`,
`claude-sonnet-4-5`, or `llama3.1:8b` (for Ollama, one already pulled
there). There is no built-in source or model: until one is chosen, in AI
Settings or as a server default, generation says none is configured.

**Choosing a source.** Each account chooses its own source and model in AI
Settings and keeps them with **Save AI Settings** — stored with the account
on the server, so the web and terminal interfaces share them. Switching
source is just a change in AI Settings; documents are not tied to a
provider.

**Supplying keys and addresses.** Either place works for every source:

- **Per account** — the **Connection** fields in AI Settings. **API Key** is
  the key for `openai` or `anthropic` (ignored for `ollama`); **Server URL**
  is the endpoint for whichever source is selected. They are saved with
  the account, apply only to that account's requests, and take precedence
  over the server's environment. They are hidden when the server runs with
  `--disable-custom-env-vars` (or `ALLOW_CUSTOM_ENV_VARS=false`).
- **Server-wide** — the environment variables in the table, set where the
  server starts: `export` before `writing-assistant`, `Environment=` in a
  systemd unit, `-e` or `.env` for a container (see
  [Connecting the Container to an LLM](CONTAINER_DEPLOYMENT.md#connecting-the-container-to-an-llm)).
  They are read when the server starts.

**OpenAI-compatible servers:** choose `openai` as the source, put the
server's base URL in **Server URL** (usually ending in `/v1`, e.g.
`http://localhost:1234/v1`), and set **API Key** to whatever it expects —
any non-empty value if it does not check one. The server must implement
OpenAI's Responses API (`/v1/responses`), which TalkPipe's `openai` source
uses rather than Chat Completions; Test Connection shows whether it does.

Press **Test Connection** after any change: it makes a real, token-capped
request through the selected source and model and reports what is wrong —
missing or rejected key, unreachable server, unknown model.

### Server default (administrators)

To give every account a working model without each user visiting AI
Settings, set TalkPipe's default source and model — and that source's key
or address — in the server's environment before starting it. Accounts that
leave AI Source on "Server default" and Model blank then use it; a source
or model a user picks in AI Settings takes precedence.

```bash
# A cloud API ...
export TALKPIPE_DEFAULT_MODEL_SOURCE=openai        # openai | anthropic | ollama
export TALKPIPE_DEFAULT_MODEL_NAME=gpt-4o
export OPENAI_API_KEY="sk-your-api-key-here"
# ... or an Ollama server:
#   export TALKPIPE_DEFAULT_MODEL_SOURCE=ollama
#   export TALKPIPE_DEFAULT_MODEL_NAME=llama3.1:8b
#   export TALKPIPE_OLLAMA_SERVER_URL="http://your-ollama-host:11434"   # if not local
writing-assistant --host 0.0.0.0 --disable-custom-env-vars
```

The same keys can go in `~/.talkpipe.toml` (`default_model_source = "ollama"`,
`default_model_name = "llama3.1:8b"`) of the account running the server;
environment variables override the file. API keys belong in the
environment, not the file — the provider SDKs read only the environment.
**Test Connection** with the Server-default source reports which model the
server resolved.

TalkPipe's
[model and source configuration guide](https://github.com/sandialabs/talkpipe/blob/stable/docs/guides/model-and-source-configuration.md)
covers these settings in more depth.

## Terminal interface (TUI)

Everything the web interface does is also available from a terminal, for
places where a browser is not an option (an SSH session, a tmux window, a
headless box). The TUI is a client of the same server, so it shares your
account, documents, snapshots, and settings with the web UI.

```bash
# 1. Start the server (in another terminal, tmux pane, or as a service)
writing-assistant

# 2. Open the terminal interface
writing-assistant-tui
```

**No server? Let the TUI start one.** `writing-assistant-tui --standalone`
runs the server inside the TUI's own process, on localhost only, and stops
it when you quit — one command, nothing to keep running. It is the same
server `writing-assistant` starts, with the same database, JWT secret and
AI configuration (`WRITING_ASSISTANT_DB_PATH`, `WRITING_ASSISTANT_SECRET`,
and the [provider variables](#llm-providers) such as `OPENAI_API_KEY` or
`TALKPIPE_OLLAMA_SERVER_URL`, … from the environment), so your documents
and login are the same whichever way you run it, and a browser on the same
machine can open http://localhost:8001 while the TUI is up. It listens on
port 8001 (`--port <n>` or `WRITING_ASSISTANT_PORT` to change it) and refuses
to start if that port is taken — if the thing on it is a writing-assistant
server, just drop the flag. Its log goes to `tui_server.log` next to the
session file, since the terminal belongs to the TUI. The standalone server
only lives as long as the TUI does; for one that other machines or other
terminals share, start it separately as follows.

**Keeping the server running.** The server must outlive the terminal you
started it in. On a headless or SSH-only machine the simplest way is a tmux
session (`tmux new -d -s writing-assistant writing-assistant`; reattach with
`tmux attach -t writing-assistant`). To have it start at login and restart
on failure, install it as a systemd user service — put the following in
`~/.config/systemd/user/writing-assistant.service` (set `ExecStart` to the
path `which writing-assistant` prints with the virtual environment active —
the example assumes the venv from the install steps lives in
`~/talkpipe-writing-assistant` — and add any `Environment=` lines you need,
e.g. the [provider variables](#llm-providers) `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY` or `TALKPIPE_OLLAMA_SERVER_URL`), then
`systemctl --user enable --now writing-assistant`:

```ini
[Unit]
Description=TalkPipe Writing Assistant server

[Service]
ExecStart=%h/talkpipe-writing-assistant/.venv/bin/writing-assistant
Restart=on-failure

[Install]
WantedBy=default.target
```

Run `loginctl enable-linger $USER` once if the service should also run while
you are not logged in. The container images in
[CONTAINER_DEPLOYMENT.md](CONTAINER_DEPLOYMENT.md) are the other option.

Log in (or choose **Create an account**) on the first screen — the server
URL defaults to `http://localhost:8001`; pass `--server http://host:port` or
set `WRITING_ASSISTANT_TUI_SERVER` if the server runs on another machine or
port (for example after `writing-assistant --port 8080`). The editor then
works like the web one: a title field, the document (leave a blank line
between sections), and a suggestion panel that follows the section under
the cursor. The cursor starts in the document body, so type your text
straight away; press `Shift+Tab` to reach the title field above it.

Before asking for suggestions, tell the TUI which model to use: press `F3`,
press `F3` again to switch to the **AI Settings** tab (or `Left`/`Right`
with the tab bar focused), choose the AI source (`Enter` opens the
dropdown) and enter a model name (see [LLM providers](#llm-providers); an
API key for OpenAI or Anthropic, or the address of an Ollama server on
another machine, goes in the **API key** / **Server URL** fields on the
same tab, or in the server's environment), press **Test Connection**, then
**Save AI Settings**. The choice is stored with your
account, so the web interface uses it too. If the administrator configured
a server default, leave the source on "Server default" and the model blank
— Test Connection shows which model the server resolves.

| Key | Action |
|-----|--------|
| `F5` / `F6` / `F7` / `F8` | Ideas / Rewrite / Improve / Proofread the current section (`Ctrl+G` also runs Ideas). A request made while another is still generating is queued and runs next |
| `Ctrl+U` | Use the suggestion as the section's text (for Ideas, which are advice rather than prose, it asks first) |
| `Ctrl+S` | Save (asks for a library name the first time — the document is stored on the server, shared with the web UI, not written to a file here; use File → Export for a file) |
| `Ctrl+N` / `Ctrl+O` | New document (a title and optional outline; `Ctrl+S` then stores it in your library) / Open a document from your library (type to filter the list by name or title; `Up`/`Down` and `Enter` pick one) |
| `F2` | File menu: New, Save, Save As, Open, Delete, Create snapshot, Revert to snapshot, Import, Export, Copy, Account (change email or password), Log out |
| `F3` | Settings: writing style, tone, audience, context, directive, word limit (and, below them, **Save as Template** / Apply / Delete for quick-access templates); AI source/model, Server URL, API key, environment variables, Test Connection |
| `F4` | Templates: start a new document from a saved template (see [Quick-access templates](#quick-access-templates)). The open document is saved first when it has a library name; otherwise the Save / Discard / Cancel prompt appears |
| `F1` | Help |
| `Ctrl+P` | Command palette: type part of a command's name (Save As, Create snapshot, Export, Account, Log out, …) and press `Enter` |
| `Tab` / `Shift+Tab` | Move between the title, the editor, the suggestion panel (arrow keys scroll it) and the buttons |
| `Esc` | Close a dialog or menu without changes |
| `Ctrl+Q` | Quit (asks first if there are unsaved changes — **Save**, **Discard changes** or **Cancel**; the same prompt guards Open, New, Import, Revert and Log out. `Ctrl+C` copies the editor selection and does not quit) |
| `Shift+Arrows`, `Ctrl+X`, `Ctrl+Z` / `Ctrl+Y` | Select text, cut it, undo / redo. To move a section: select it, `Ctrl+X`, put the cursor on the blank line where it belongs, `Ctrl+V`; to delete one, select it and press `Delete` |
| `Ctrl+C` / `Ctrl+V` | Copy the selection / paste — always work within the app (editor, title, and every dialog field). They also use the *system* clipboard when `wl-paste`, `xclip`, `xsel` or `pbpaste` is installed; to paste text from another program without one of those (e.g. over SSH) use the terminal's own paste — `Ctrl+Shift+V`, `Shift+Insert`, or `Shift`+middle-click |

The editor works down to 60x16 (smaller than that, it says so). Below 22
rows the mode buttons are hidden so the suggestion panel stays on screen
(F5–F8 and Ctrl+U still work), and below 90 columns the buttons use short
labels. If a suggestion comes back as several paragraphs, **Use This Text**
inserts them as several sections and puts the cursor on the first.

The login token is remembered in `~/.writing_assistant/tui_session.json`
(mode 600; set `WRITING_ASSISTANT_TUI_HOME` to move it), so the next launch
skips the login screen and reopens the last document at the section you
were working on. `writing-assistant-tui --logout` forgets the saved
session and starts at the login screen. Import/Export use the same JSON
document format as the web UI, so files move between the two freely:
Export writes that JSON to the path you give (the default is the document's
library name in the directory you started the TUI from), and the text
itself is the file's `content` field — for plain text, use **Copy document
to clipboard** in the File menu.

## Usage

### Starting the Server

```bash
# Default: http://localhost:8001, opened in your browser. If another program
# holds 8001 the next free port is used; if the assistant itself is already
# running there, the browser is opened at it and nothing else starts.
writing-assistant

# Do not open a browser (containers, servers, remote sessions)
writing-assistant --no-browser

# Custom port (an explicit port is never substituted: if it is taken, this fails)
writing-assistant --port 8080

# Custom host and port (0.0.0.0 accepts connections from other machines;
# the banner then shows this machine's name in the URLs)
writing-assistant --host 0.0.0.0 --port 8080

# Enable auto-reload for development
writing-assistant --reload

# Custom database location
writing-assistant --db-path /path/to/database.db

# Disable custom environment variables from UI (security)
writing-assistant --disable-custom-env-vars

# Initialize database without starting server
writing-assistant --init-db

# You can also use environment variables
WRITING_ASSISTANT_PORT=8080 writing-assistant
WRITING_ASSISTANT_RELOAD=true writing-assistant
WRITING_ASSISTANT_DB_PATH=/path/to/database.db writing-assistant
```

When the server starts, it will display:
- The URL to access the application
- Registration and login URLs
- API documentation URL
- Database location

**Authentication:** The application uses JWT-based multi-user authentication with FastAPI Users. Each user has their own account with secure password storage. New users can register through the web interface at `/register`, and existing users log in at `/login`. To change your email address or password once logged in, open **Settings → Account** in the web interface, or **File → Account** (F2) in the terminal interface; both ask for the current password first, and a changed email is what you log in with next time.

### Environment Variables

Configure the application with these environment variables. Only the
provider you actually use needs its variables set — see
[LLM providers](#llm-providers).

| Variable | Description | Default |
|----------|-------------|---------|
| `WRITING_ASSISTANT_HOST` | Server host address | `localhost` |
| `WRITING_ASSISTANT_PORT` | Server port number (setting it disables the free-port fallback, like `--port`) | `8001` |
| `WRITING_ASSISTANT_RELOAD` | Enable auto-reload (development) | `false` |
| `WRITING_ASSISTANT_DB_PATH` | Database file location | `~/.writing_assistant/writing_assistant.db` |
| `WRITING_ASSISTANT_SECRET` | JWT secret key for authentication | Auto-generated (change in production) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI key, and an alternate OpenAI-compatible endpoint (users can also set both per account in AI Settings → Connection) | unset |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` | Anthropic key, and an alternate Anthropic-compatible endpoint (same per-account override) | unset |
| `TALKPIPE_OLLAMA_SERVER_URL` | Ollama server URL, local or remote (same per-account override, as Server URL) | `http://localhost:11434` |
| `TALKPIPE_DEFAULT_MODEL_SOURCE` | Server-wide default AI source, used when a request leaves the source on "Server default" (`openai`, `anthropic`, `ollama`) | unset (users must choose one) |
| `TALKPIPE_DEFAULT_MODEL_NAME` | Server-wide default model name, used when a request leaves Model blank | unset |
| `ALLOW_CUSTOM_ENV_VARS` | Allow users to configure environment variables through the UI (`false` to disable) | `true` |
| `WRITING_ASSISTANT_TUI_SERVER` | Server URL for `writing-assistant-tui` (overridden by `--server`; needed when the server fell back to another port; ignored with `--standalone`, which uses `WRITING_ASSISTANT_PORT`) | last used, else `http://localhost:8001` |
| `WRITING_ASSISTANT_TUI_HOME` | Directory for the TUI's saved session (`tui_session.json`) | `~/.writing_assistant` |


**Security Options:**
- `--disable-custom-env-vars` (or `ALLOW_CUSTOM_ENV_VARS=false`): Prevents users from configuring environment variables through the browser interface
  - Use this for shared deployments or when you want centralized credential management
  - Environment variables must be set at the server level (via shell environment) — see [Server default](#server-default-administrators) for choosing the model centrally as well
  - The Connection (Server URL, API Key) and Environment Variables fields are hidden in both the web and terminal interfaces; the startup banner notes that the switch is on


**Configure document metadata**:
   - AI Source: `openai`, `anthropic`, or `ollama` (see
     [LLM providers](#llm-providers))
   - Model: e.g., `gpt-4o`, `claude-sonnet-4-5`, or `llama3.1:8b`
   - Writing style: formal, casual, technical, etc.
   - Target audience: general public, experts, students, etc.
   - Tone: neutral, persuasive, informative, etc.
   - Word limit: approximate words per paragraph

### Document Storage

Documents are stored in an SQLite database with multi-user isolation:

**Default Location:** `~/.writing_assistant/writing_assistant.db`

**Custom Location:** Use `--db-path` or `WRITING_ASSISTANT_DB_PATH` to specify an alternative location

**Features:**
- Per-user document isolation (users only see their own documents)
- Snapshots on demand (File → Create snapshot); the 10 most recent are kept per document
- User-specific preferences (AI settings, writing style, etc.)
- Cascade deletion (removing a user deletes all their documents)

**Backup:** Simply copy the database file to create a backup. The database can be moved to a different location using the `--db-path` option.

## Administration

Two console commands are installed alongside the application for user management:

```bash
# Create the first admin (superuser) account
writing-assistant-create-superuser

# Manage users (list, info, delete, reset-password, toggle-active, make-superuser)
writing-assistant-admin list
writing-assistant-admin help
```

See the [Admin Guide](ADMIN_GUIDE.md) for the full user-administration
reference and the [Container Deployment Guide](CONTAINER_DEPLOYMENT.md) for running these
commands inside a container.

## Architecture

### Package Structure

```
src/writing_assistant/
├── __init__.py          # Package initialization and version
├── core/                # Core business logic
│   ├── __init__.py
│   ├── callbacks.py     # AI text generation functionality
│   ├── definitions.py   # Data models (Metadata)
│   └── segments.py      # TalkPipe segment registration
├── app/                 # Web application
│   ├── __init__.py
│   ├── main.py          # FastAPI application and API endpoints
│   ├── server.py        # Application entry point
│   ├── static/          # CSS and JavaScript assets
│   └── templates/       # Jinja2 HTML templates
└── tui/                 # Terminal interface (Textual), a client of the REST API
    ├── app.py           # Screens, dialogs, key bindings; `writing-assistant-tui`
    ├── app.tcss         # Styling
    ├── client.py        # Async HTTP client for the server's API
    ├── sections.py      # Section parsing / suggestion tracking (mirrors script.js)
    └── session.py       # Saved server URL, token, last document
```

### Core Components

- **Metadata**: Configuration for writing style, audience, tone, and AI settings
- **Section**: Individual document sections with async text generation and queuing
- **Document**: Complete document with sections, metadata, and snapshot management
- **Callbacks**: AI text generation using TalkPipe with context-aware prompting

### Customizing Generation

The prompt templates and the four generation modes (rewrite, improve,
proofread, ideas) live in `src/writing_assistant/core/callbacks.py`, built on
TalkPipe's `LLMPrompt` segment. To change how text is generated — adjust the
prompts or swap in a different TalkPipe pipeline — edit that module, install
the checkout (`pip install -e .`; after that, edits only need the server
restarted), and start `writing-assistant` again. To add a whole new mode,
register its name in `GENERATION_MODES` in `callbacks.py` and give it a
branch in `get_system_prompt()` — the server rejects a mode it does not know
with a 400 that lists the known ones rather than quietly answering with
another mode's prompt — then add its button to the web UI: a `.mode-btn`
element in `src/writing_assistant/app/templates/index.html` whose
`data-mode` is the new name (`script.js` sends that attribute as the mode, so
it needs no change), and a tuple in `GENERATION_MODES` in
`src/writing_assistant/tui/app.py` for the TUI. Changing the model
provider needs no code change: see [LLM providers](#llm-providers).


## Troubleshooting

### Application Issues

**"Port already in use"**
- Change the port: `writing-assistant --port 8080`
- Or kill the process using the port

**"Cannot save document"** or **"Database error"**
- Check write permissions to the database directory (default: `~/.writing_assistant/`)
- Ensure the directory exists: `mkdir -p ~/.writing_assistant`
- Try a different database location: `writing-assistant --db-path /tmp/test.db`
- Initialize the database manually: `writing-assistant --init-db`

**"Authentication failed"** or **"Invalid credentials"**
- Double-check your email and password
- Register a new account if you haven't already
- The database may have been reset - check the database location

**"Cannot connect to database"**
- Verify the database file exists and is not corrupted
- Check file permissions on the database file
- Try initializing a new database: `writing-assistant --db-path /tmp/new.db --init-db`


## Releasing

The release process — tag conventions, the manual application test that
must pass before tagging, and the publish steps — is in
[RELEASING.md](RELEASING.md).

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/sandialabs/talkpipe-writing-assistant/blob/master/LICENSE) file for details.

## Acknowledgments

Built with [TalkPipe](https://github.com/sandialabs/talkpipe), a flexible framework for AI pipeline construction developed at Sandia National Laboratories.