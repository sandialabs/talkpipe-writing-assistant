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
- **Flexible AI Backend**: Works with LLM endpoints including OpenAI (GPT-4, GPT-4o), Anthropic (Claude 3.5 Sonnet, Claude 3 Opus), and Ollama (llama3, mistral, etc.)
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
- Access to an LLM endpoint: OpenAI, Anthropic, Ollama (local), or any compatible endpoint

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

Then navigate to `http://localhost:8001` in your browser. See the [Quick Start](#quick-start) section below for next steps.

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
pip install -e .[dev]
```

### Development environment (uv, with a reproducible lock)

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

**TL;DR:** After `pip install talkpipe-writing-assistant`, just run `writing-assistant` and open `http://localhost:8001` in your browser!

After installing with pip, follow these steps to get started:

### 1. Start the Server

```bash
writing-assistant
```

The server will start on `http://localhost:8001` and display:

```
🔐 Writing Assistant Server - Multi-User Edition
📝 Access your writing assistant at: http://localhost:8001/
🔑 Register a new account at: http://localhost:8001/register
🔐 Login at: http://localhost:8001/login
📚 API documentation: http://localhost:8001/docs
💾 Database: /home/user/.writing_assistant/writing_assistant.db
```

### 2. Create Your Account

1. Open your browser and navigate to `http://localhost:8001/register`
2. Enter your email address and password
3. Click "Create Account", then log in on the login page

### 3. Configure AI Backend

Point the application at an LLM endpoint — OpenAI, Anthropic, and Ollama are supported out of the box:

**Option A: OpenAI (Cloud)**
1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Set your API key:
   ```bash
   export OPENAI_API_KEY="sk-your-api-key-here"
   ```
3. In the web interface: Settings → AI Settings → Set Source to `openai` and Model to your model of choice (in the terminal interface: `F3` → AI Settings).

**Option B: Anthropic (Cloud)**
1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Set your API key:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
   ```
3. In the web interface: Settings → AI Settings → Set Source to `anthropic` and Model to your model of choice (in the terminal interface: `F3` → AI Settings).

**Option C: Ollama (Local, Free)**
1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull [model name]`
3. Start Ollama: `ollama serve`
4. In the web interface: Settings → AI Settings → Set Source to `ollama` and Model to [model name] (in the terminal interface: `F3` → AI Settings)

If Ollama runs on a different machine (or a non-default port), set
`TALKPIPE_OLLAMA_SERVER_URL` before starting the server (if the server is
already running, stop it and start it again with the variable set):

```bash
export TALKPIPE_OLLAMA_SERVER_URL="http://your-ollama-host:11434"
writing-assistant
```

Alternatively, set it without restarting the server: in the web interface,
open Settings → AI Settings → Connection and enter the address in **Server
URL**. Values set this way are stored in your browser and applied per
generation request (unless the server was started with
`--disable-custom-env-vars`).

The Connection fields apply to whichever source is selected: **Server
URL** is an alternate API endpoint for `openai`/`anthropic` or the Ollama
server for `ollama`, and **API Key** supplies your key for the cloud
sources. Use the **Test Connection** button to verify the settings with a
real round trip before generating — it reports exactly what is wrong
(missing key, unreachable server, model not pulled) on failure.

> **Note:** AI Source is a dropdown offering `openai`, `anthropic`, and
> `ollama`, plus "Server default", which defers to the source configured on
> the server (TalkPipe configuration).

**Server default (administrators):** to give every account a working model
without each user visiting AI Settings, set TalkPipe's default source and
model in the server's environment before starting it — users who leave AI
Source on "Server default" and Model blank then use it:

```bash
export TALKPIPE_DEFAULT_MODEL_SOURCE=ollama
export TALKPIPE_DEFAULT_MODEL_NAME=llama3.1:8b
export TALKPIPE_OLLAMA_SERVER_URL="http://your-ollama-host:11434"   # if not local
writing-assistant --host 0.0.0.0 --disable-custom-env-vars
```

The same keys can go in `~/.talkpipe.toml` (`default_model_source = "ollama"`,
`default_model_name = "llama3.1:8b"`) of the account running the server;
environment variables override the file. **Test Connection** with the
Server-default source reports which model the server resolved. Any source
or model a user picks in AI Settings takes precedence over the default.

### 4. Start Writing!

1. After logging in, the editor opens directly — add a title and start typing.
   Leave a blank line between sections (paragraphs).
2. Place your cursor in a section, then click one of the generation buttons
   below the editor — **Ideas**, **Rewrite**, **Improve**, or **Proofread** —
   to create AI-assisted content for that section.
3. When you like a suggestion, click **"← Use This Text"** to replace the
   section with it.
4. Save your work via the **File ▾** menu (**File → Save**); the File menu also
   offers Save As, Open, snapshots, and import/export.

That's it! You're ready to use the AI writing assistant.

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

Log in (or choose **Create an account**) on the first screen — the server
URL defaults to `http://localhost:8001`; pass `--server http://host:port` or
set `WRITING_ASSISTANT_TUI_SERVER` if the server runs on another machine or
port (for example after `writing-assistant --port 8080`). The editor then
works like the web one: a title field, the document (leave a blank line
between sections), and a suggestion panel that follows the section under
the cursor.

Before asking for suggestions, tell the TUI which model to use: press `F3`,
press `F3` again to switch to the **AI Settings** tab (or `Left`/`Right`
with the tab bar focused), choose the AI source (`Enter` opens the
dropdown) and enter a model name (see
[Configure AI Backend](#3-configure-ai-backend)), press **Test
Connection**, then **Save AI Settings**. The choice is stored with your
account, so the web interface uses it too. If the administrator configured
a server default, leave the source on "Server default" and the model blank
— Test Connection shows which model the server resolves.

| Key | Action |
|-----|--------|
| `F5` / `F6` / `F7` / `F8` | Ideas / Rewrite / Improve / Proofread the current section |
| `Ctrl+U` | Use the suggestion as the section's text |
| `Ctrl+S` | Save (asks for a filename the first time) |
| `Ctrl+N` / `Ctrl+O` | New document / Open a document from your library |
| `F2` | File menu: New, Save, Save As, Open, Delete, Create snapshot, Revert to snapshot, Import, Export, Copy, Log out |
| `F3` | Settings: writing style, tone, audience, context, directive, word limit; AI source/model, Server URL, API key, environment variables, Test Connection |
| `F1` | Help |
| `Tab` / `Shift+Tab` | Move between the title, the editor, the suggestion panel (arrow keys scroll it) and the buttons |
| `Esc` | Close a dialog or menu without changes |
| `Ctrl+Q` | Quit (asks first if there are unsaved changes; `Ctrl+C` copies the editor selection and does not quit) |
| `Ctrl+C` / `Ctrl+V` | Copy the selection / paste — in the editor, the title, and every dialog field. `Ctrl+V` reads the system clipboard when `wl-paste`, `xclip`, `xsel` or `pbpaste` is installed; without one (e.g. over SSH) use the terminal's own paste — `Ctrl+Shift+V`, `Shift+Insert`, or `Shift`+middle-click |

The editor works down to 60x16. Below 22 rows the mode buttons are hidden so
the suggestion panel stays on screen (F5–F8 and Ctrl+U still work), and
below 80 columns the buttons use short labels. If a suggestion comes back
as several paragraphs, **Use This Text** inserts them as several sections.

The login token is remembered in `~/.writing_assistant/tui_session.json`
(mode 600; set `WRITING_ASSISTANT_TUI_HOME` to move it), so the next launch
skips the login screen and reopens the last document at the section you
were working on. `writing-assistant-tui --logout` forgets the saved
session. Import/Export use the same JSON
document format as the web UI, so files move between the two freely.

## Usage

### Starting the Server

```bash
# Default: http://localhost:8001
writing-assistant

# Custom port
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

**Authentication:** The application uses JWT-based multi-user authentication with FastAPI Users. Each user has their own account with secure password storage. New users can register through the web interface at `/register`, and existing users log in at `/login`.

### Environment Variables

Configure the application with these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `WRITING_ASSISTANT_HOST` | Server host address | `localhost` |
| `WRITING_ASSISTANT_PORT` | Server port number | `8001` |
| `WRITING_ASSISTANT_RELOAD` | Enable auto-reload (development) | `false` |
| `WRITING_ASSISTANT_DB_PATH` | Database file location | `~/.writing_assistant/writing_assistant.db` |
| `WRITING_ASSISTANT_SECRET` | JWT secret key for authentication | Auto-generated (change in production) |
| `TALKPIPE_OLLAMA_SERVER_URL` | Ollama server URL for local models | `http://localhost:11434` |
| `TALKPIPE_DEFAULT_MODEL_SOURCE` | Server-wide default AI source, used when a request leaves the source on "Server default" (`openai`, `anthropic`, `ollama`) | unset (users must choose one) |
| `TALKPIPE_DEFAULT_MODEL_NAME` | Server-wide default model name, used when a request leaves Model blank | unset |
| `ALLOW_CUSTOM_ENV_VARS` | Allow users to configure environment variables through the UI (`false` to disable) | `true` |
| `WRITING_ASSISTANT_TUI_SERVER` | Server URL for `writing-assistant-tui` (overridden by `--server`) | last used, else `http://localhost:8001` |
| `WRITING_ASSISTANT_TUI_HOME` | Directory for the TUI's saved session (`tui_session.json`) | `~/.writing_assistant` |


**Security Options:**
- `--disable-custom-env-vars` (or `ALLOW_CUSTOM_ENV_VARS=false`): Prevents users from configuring environment variables through the browser interface
  - Use this for shared deployments or when you want centralized credential management
  - Environment variables must be set at the server level (via shell environment) — see the server default above for choosing the model centrally as well
  - The Connection (Server URL, API Key) and Environment Variables fields are hidden in both the web and terminal interfaces; the startup banner notes that the switch is on


**Configure document metadata**:
   - AI Source: `openai`, `anthropic`, or `ollama`
   - Model: e.g., `gpt-4`, `claude-3-5-sonnet-20241022`, or `llama3.1:8b`
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
prompts or swap in a different TalkPipe pipeline — edit that module and
reinstall (`pip install -e .` from a checkout). To add a whole new mode you
also need to add its button to the web UI: the mode buttons are defined in
`src/writing_assistant/app/templates/index.html` (the `.mode-btn` elements)
and sent by `src/writing_assistant/app/static/script.js` — and to the TUI,
in `GENERATION_MODES` in `src/writing_assistant/tui/app.py`. Any backend with
an OpenAI-, Anthropic-, or Ollama-compatible endpoint works; point the
provider API key / base URL settings (or `TALKPIPE_OLLAMA_SERVER_URL` for
Ollama) at your endpoint and select the source/model in Settings → AI
Settings.


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


## License

This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/sandialabs/talkpipe-writing-assistant/blob/master/LICENSE) file for details.

## Acknowledgments

Built with [TalkPipe](https://github.com/sandialabs/talkpipe), a flexible framework for AI pipeline construction developed at Sandia National Laboratories.