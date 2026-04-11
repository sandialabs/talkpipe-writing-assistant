<center><img src="docs/logo.png" width=400></center>

# TalkPipe Writing Assistant

Making the AI write _with_ you, not _for_ you.

An AI-powered writing assistant that transforms how you create structured documents. This application combines intelligent content generation with intuitive document management, enabling writers to craft professional documents with contextually-aware AI assistance that understands your style, audience, and objectives.

Built on the [TalkPipe framework](https://github.com/sandialabs/talkpipe), this tool helps you:

- **Break writer's block**: Generate initial drafts and ideas for any section
- **Maintain consistency**: AI understands your document's context, style, and tone across all sections
- **Iterate quickly**: Multiple generation modes (rewrite, improve, proofread, ideas) let you refine content efficiently
- **Stay organized**: Structure documents into sections with main points and supporting text
- **Work offline**: Use local LLMs via Ollama or cloud-based models via OpenAI, Anthropic, and more

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
- **Document Management**: Save, load, and manage multiple documents with automatic snapshots
- **User Preferences**: Per-user AI settings, writing style, and environment variables
- **Customizable Metadata**: Configure writing style, tone, audience, and generation parameters
- **Flexible AI Backend**: Support for OpenAI (GPT-4, GPT-4o), Anthropic (Claude 3.5 Sonnet, Claude 3 Opus), and Ollama (llama3, mistral, etc.)
- **Database Storage**: SQLite database with configurable location for easy backup and deployment
- **Async Processing**: Efficient queuing system for AI generation requests

## Pre-built container (Docker or Podman)

CI publishes images to [**GitHub Container Registry**](https://github.com/sandialabs/talkpipe-writing-assistant/pkgs/container/talkpipe-writing-assistant):

| | |
|--|--|
| **Image** | `ghcr.io/sandialabs/talkpipe-writing-assistant` |
| **Platforms** | Linux **amd64** and **arm64** (release builds). The app runs in a **Linux** container; on Windows and macOS use [Docker Desktop](https://docs.docker.com/desktop/) or [Podman](https://podman.io/) (they run Linux containers under the hood). |

**Tags (typical):** `latest` — stable GitHub Release (not marked pre-release); `experimental` — pushes to the `develop` branch or a pre-release GitHub Release; branch names (e.g. `main`) and commit SHAs are also published. Check the package page for the exact tag after a workflow run.

**Registry login:** This package is **public**, so you can **`pull` and `run` without logging in** to GHCR. You only need `docker login ghcr.io` / `podman login ghcr.io` if the image is **private**, your organization requires it, or `pull` fails with an authentication error (use a GitHub [Personal Access Token](https://github.com/settings/tokens) with **`read:packages`** as the password).

1. **`pull` is optional.** **`docker run` / `podman run` pulls the image automatically** if it is not already local (same on Windows). Use an explicit `docker pull` / `podman pull` only if you want to download separately.

   **Typo:** the subcommand appears only once — use `podman pull ghcr.io/...` or `podman run ...`, never `podman pull pull ...` (the second `pull` is treated as an image name and triggers errors about `docker.io/library/pull`).

2. **Run** — persist the database under `/app/data` (the image supplies defaults, including a JWT secret):

   ```bash
   docker run --rm -p 8001:8001 \
     -v wa_data:/app/data \
     ghcr.io/sandialabs/talkpipe-writing-assistant:latest
   ```

   Open **http://localhost:8001** or **http://127.0.0.1:8001** (use **`http`**, not `https`). Use `podman run` with the same flags if you use Podman.

   **Volume syntax:** `-v` is `host:container`. The path after the second `:` must be an **absolute path inside the container** — use **`/app/data`**, not `.` or a relative path.

### Windows (Command Prompt or PowerShell)

You do **not** have to **`pull` first** — **`run` is enough** (it will fetch the image if needed). Examples on one line:

```bat
docker run --rm -p 8001:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
```

```bat
podman run --rm -p 8001:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
```

Optional: download the image ahead of time with `docker pull …` or `podman pull …` — **only one** `pull` in the command (see typo note above).

Start **Docker Desktop** or your **Podman** machine before running. Stop the container with **Ctrl+C** in that terminal.

### If the browser cannot connect

1. **Confirm the app is reachable from the host** (while the container is running):

   ```bat
   curl http://127.0.0.1:8001/
   ```

   If this fails, fix networking before blaming the browser. Check `docker ps` or `podman ps` and ensure the **PORTS** column shows something like `8001->8001` (or `0.0.0.0:8001->8001/tcp`).

2. **Bind the host port explicitly** (helps some Windows / Podman setups):

   ```bat
   docker run --rm -p 127.0.0.1:8001:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
   ```

   Use `podman run` with the same `-p` and `-v` flags if you use Podman.

3. **Port already in use** — map a different host port (here **8080**):

   ```bat
   docker run --rm -p 127.0.0.1:8080:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
   ```

   Then open **http://127.0.0.1:8080**.

4. **Podman on Windows** — if `curl` to `127.0.0.1` still fails, restart the VM (`podman machine stop` then `podman machine start`) or update **Podman / Podman Desktop**; older builds sometimes break `localhost` port forwarding from the host into the machine.

5. **Firewall or VPN** — allow the container engine through **Windows Defender Firewall** (private networks) or briefly disconnect VPN to test.

To build and run from a **local clone** with Compose (including dev reload), see [Using Docker](#using-docker) below.

## Installation

### Prerequisites

- Python 3.11 or higher
- An AI backend: OpenAI, Anthropic, or Ollama (local)

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

### Development with uv (reproducible dependency lock)

The repo includes [`uv.lock`](uv.lock) so CI and local installs can use the same resolved versions. Install [uv](https://github.com/astral-sh/uv), then:

```bash
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd talkpipe-writing-assistant
uv sync --frozen --extra dev
```

Run tests and tools via the project environment, for example `uv run pytest`, or activate the virtualenv (`.venv` on Unix: `source .venv/bin/activate`).

After changing dependencies in `pyproject.toml`, refresh the lockfile with `uv lock` and commit `uv.lock`. To bump versions, use `uv lock --upgrade` or `uv lock --upgrade-package <name>`.

### Using Docker

Build and run from the repository (as opposed to the [pre-built GHCR image](#pre-built-container-docker-or-podman) above):

```bash
# Production deployment
docker-compose up talkpipe-writing-assistant

# Development with live reload
docker-compose --profile dev up talkpipe-writing-assistant-dev
```

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
3. Click "Register" to create your account

### 3. Configure AI Backend

You need to configure one of the supported AI backends:

**Option A: OpenAI (Cloud)**
1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Set your API key:
   ```bash
   export OPENAI_API_KEY="sk-your-api-key-here"
   ```
3. In the web interface: Settings → AI Settings → Set Source to `openai` and Model to your model of choice.

**Option B: Anthropic (Cloud)**
1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Set your API key:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-your-api-key-here"
   ```
3. In the web interface: Settings → AI Settings → Set Source to `anthropic` and Model to your model of choice.

**Option C: Ollama (Local, Free)**
1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull [model name]`
3. Start Ollama: `ollama serve`
4. In the web interface: Settings → AI Settings → Set Source to `ollama` and Model to [model name]

### 4. Start Writing!

1. Click "Create New Document"
2. Add a title and sections, leaving a blank line between sections.
3. Click "Generate" on any section to create AI-assisted content
4. Save your work with the "Save Document" button

That's it! You're ready to use the AI writing assistant.

## Usage

### Starting the Server

```bash
# Default: http://localhost:8001
writing-assistant

# Custom port
writing-assistant --port 8080

# Custom host and port
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


**Security Options:**
- `--disable-custom-env-vars`: Prevents users from configuring environment variables through the browser interface
  - Use this for shared deployments or when you want centralized credential management
  - Environment variables must be set at the server level (via shell environment)
  - The Environment Variables section will be hidden in the UI


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
- Automatic snapshot management (keeps 10 most recent versions)
- User-specific preferences (AI settings, writing style, etc.)
- Cascade deletion (removing a user deletes all their documents)

**Backup:** Simply copy the database file to create a backup. The database can be moved to a different location using the `--db-path` option.

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
└── app/                 # Web application
    ├── __init__.py
    ├── main.py          # FastAPI application and API endpoints
    ├── server.py        # Application entry point
    ├── static/          # CSS and JavaScript assets
    └── templates/       # Jinja2 HTML templates
```

### Core Components

- **Metadata**: Configuration for writing style, audience, tone, and AI settings
- **Section**: Individual document sections with async text generation and queuing
- **Document**: Complete document with sections, metadata, and snapshot management
- **Callbacks**: AI text generation using TalkPipe with context-aware prompting


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