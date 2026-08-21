# Container Deployment Guide (Podman or Docker)

This guide explains how to deploy the Writing Assistant in a container.

Commands below use **Podman** (`podman`, `podman-compose`). **Docker is fully
compatible**: substitute `docker` for `podman` and `docker-compose` (or
`docker compose`) for `podman-compose` — the arguments are identical.

> **Compose version note:** the compose file declares an *optional* `.env`
> file (`env_file: {path: .env, required: false}`). This long-form syntax
> needs podman-compose ≥ 1.1 or Docker Compose ≥ 2.24. On older versions,
> create an empty `.env` (`touch .env`) if compose complains about it.

## Running the Pre-built Image

CI publishes a public image to
[GitHub Container Registry](https://github.com/sandialabs/talkpipe-writing-assistant/pkgs/container/talkpipe-writing-assistant):

| | |
|--|--|
| **Image** | `ghcr.io/sandialabs/talkpipe-writing-assistant` |
| **Platforms** | Linux **amd64** and **arm64** (release builds). The app runs in a **Linux** container; on Windows and macOS use [Podman](https://podman.io/) / Podman Desktop or [Docker Desktop](https://docs.docker.com/desktop/) (they run Linux containers under the hood). |

**Tags (typical):** `latest` — stable GitHub Release (not marked pre-release);
`experimental` — a pre-release GitHub Release; branch names (e.g. `main`) and
commit SHAs are also published. Check the package page for the exact tag
after a workflow run.

**Registry login:** This package is **public**, so you can `pull` and `run`
without logging in to GHCR. You only need `podman login ghcr.io` if the image
is private, your organization requires it, or `pull` fails with an
authentication error (use a GitHub
[Personal Access Token](https://github.com/settings/tokens) with
`read:packages` as the password).

1. **`pull` is optional.** `podman run` pulls the image automatically if it
   is not already local (same on Windows). Use an explicit `podman pull` only
   if you want to download separately.

   **Typo warning:** the subcommand appears only once — use
   `podman pull ghcr.io/...` or `podman run ...`, never `podman pull pull ...`
   (the second `pull` is treated as an image name and triggers errors about
   `docker.io/library/pull`).

2. **Run** — persist the database under `/app/data` (the image supplies
   defaults, including a JWT secret):

   ```bash
   podman run --rm -p 8001:8001 \
     -v wa_data:/app/data \
     --add-host=host.containers.internal:host-gateway \
     ghcr.io/sandialabs/talkpipe-writing-assistant:latest
   ```

   Open **http://localhost:8001** or **http://127.0.0.1:8001** (use **`http`**,
   not `https`).

   The `--add-host` flag makes the machine running the container reachable
   from inside it as `host.containers.internal` — you need that to use an
   Ollama server running on your own machine (see
   [Connecting the Container to an LLM](#connecting-the-container-to-an-llm)).
   It is harmless otherwise, and unnecessary if you only use cloud APIs.

   **Volume syntax:** `-v` is `host:container`. The path after the second `:`
   must be an **absolute path inside the container** — use **`/app/data`**,
   not `.` or a relative path.

### Windows (Command Prompt or PowerShell)

You do **not** have to `pull` first — `run` is enough (it will fetch the image
if needed). Example on one line:

```bat
podman run --rm -p 8001:8001 -v wa_data:/app/data --add-host=host.containers.internal:host-gateway ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
```

Start your **Podman machine** (or **Docker Desktop**) before running. Stop the
container with **Ctrl+C** in that terminal.

### If the browser cannot connect

1. **Confirm the app is reachable from the host** (while the container is
   running):

   ```bash
   curl http://127.0.0.1:8001/
   ```

   If this fails, fix networking before blaming the browser. Check
   `podman ps` and ensure the **PORTS** column shows something like
   `8001->8001` (or `0.0.0.0:8001->8001/tcp`).

2. **Bind the host port explicitly** (helps some Windows / Podman setups):

   ```bash
   podman run --rm -p 127.0.0.1:8001:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
   ```

3. **Port already in use** — rootless Podman reports this as
   `rootlessport listen tcp 0.0.0.0:8001: bind: address already in use`.
   Stop whatever holds the port, or map a different host port (here **8080**):

   ```bash
   podman run --rm -p 127.0.0.1:8080:8001 -v wa_data:/app/data ghcr.io/sandialabs/talkpipe-writing-assistant:experimental
   ```

   Then open **http://127.0.0.1:8080**.

4. **Podman on Windows** — if `curl` to `127.0.0.1` still fails, restart the
   VM (`podman machine stop` then `podman machine start`) or update
   **Podman / Podman Desktop**; older builds sometimes break `localhost` port
   forwarding from the host into the machine.

5. **Firewall or VPN** — allow the container engine through the firewall
   (e.g. **Windows Defender Firewall**, private networks) or briefly
   disconnect VPN to test.

## Connecting the Container to an LLM

The application generates text through TalkPipe, which works with LLM
endpoints including **OpenAI**, **Anthropic**, and **Ollama**. Nothing in the image restricts
outbound network access — if a connection fails, it is almost always one of
the two issues below.

**Verify with Test Connection:** after logging in, open **Settings → AI
Settings** and click **Test Connection**. It performs a real, token-capped
round trip through the selected source/model and reports an actionable
error message on failure (bad key, wrong URL, model not pulled, unreachable
host, ...). Use it after every configuration change.

> **Image too old?** The Connection section (Server URL / API Key fields and
> the Test Connection button) is a recent addition. If **Settings → AI
> Settings** in your container has no Connection section, the image predates
> the feature — pull a newer tag (e.g. `experimental`, or `latest` once the
> next stable release is published) or build from the current source.

### Cloud APIs (OpenAI, Anthropic)

The container only needs ordinary outbound internet access. Provide keys
either:

- **Server-wide** — pass them when starting the container:

  ```bash
  podman run --rm -p 8001:8001 -v wa_data:/app/data \
    -e OPENAI_API_KEY=sk-... \
    -e ANTHROPIC_API_KEY=sk-ant-... \
    ghcr.io/sandialabs/talkpipe-writing-assistant:latest
  ```

  (With compose, put them in `.env` — the compose file loads it.)

- **Per-user** — each user enters an API key under **Settings → AI Settings
  → Connection**. Per-user values are applied only for that user's requests
  and require `ALLOW_CUSTOM_ENV_VARS` to be enabled (the default).

If your organization routes traffic through an OpenAI/Anthropic-compatible
gateway, set its base URL in the same Connection section (or server-wide via
`OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL`).

### Ollama

**The #1 pitfall:** inside a container, `localhost` refers to the container
itself — not your machine. An Ollama server running on the machine that
hosts the container is **not** at `http://localhost:11434` from the
container's point of view.

| Where Ollama runs | Server URL to use |
|---|---|
| On the machine hosting the container | `http://host.containers.internal:11434` (requires the `--add-host` flag above; compose sets it automatically via `extra_hosts`) |
| On another machine on your network | `http://that-machine.example:11434` |
| In another container on the same compose network | `http://<service-name>:11434` |

Set the URL either per-user (**Settings → AI Settings → Connection → Server
URL**) or server-wide (`-e TALKPIPE_OLLAMA_SERVER_URL=...` /  `.env`).

Also make sure Ollama itself accepts remote connections: by default it binds
only to `127.0.0.1`, so a request arriving over the host gateway is refused.
Start it with `OLLAMA_HOST=0.0.0.0 ollama serve` (or an equivalently scoped
bind address) on the Ollama machine.

## Building from a Local Clone

### 1. Using Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd talkpipe-writing-assistant

# Generate a secure secret
python -c "import secrets; print(secrets.token_urlsafe(32))" > .secret

# Create environment file
# (add OPENAI_API_KEY=... or ANTHROPIC_API_KEY=... lines if you use a cloud
# backend — but don't put comments on the same line as a value: in .env
# files an inline `# comment` becomes part of the value)
cat > .env << EOF
WRITING_ASSISTANT_SECRET=$(cat .secret)
EOF

# Start the production service
podman-compose up -d writing-assistant

# Check logs
podman-compose logs -f writing-assistant

# Create the first admin user (in another terminal)
podman-compose exec writing-assistant writing-assistant-create-superuser
```

> **Note:** do not add `-it` to `podman-compose exec` — podman-compose
> rejects the flag (`error: unrecognized arguments: -it`). `exec` is
> interactive by default; the same is true of `docker compose exec`.

Access the application at: `http://localhost:8001`

> **Heads-up:** `podman-compose up` builds the image (several minutes)
> *before* it validates container options such as `env_file`, so a
> configuration mistake can surface only after the build finishes.

### 2. Using Podman Directly

```bash
# Build the image
podman build -t writing-assistant .

# Run the container
podman run -d \
  --name writing-assistant \
  -p 8001:8001 \
  -v writing-assistant-db:/app/data \
  -e WRITING_ASSISTANT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
  writing-assistant

# Create admin user
podman exec -it writing-assistant writing-assistant-create-superuser
```

### Image Version Metadata

The build context excludes `.git`, so setuptools_scm cannot derive the
package version inside the build; without help the image reports the
fallback version `0.1.0`. Pass the real version as a build argument:

```bash
# Direct build
podman build --build-arg APP_VERSION="$(python3 -m setuptools_scm)" -t writing-assistant .

# Compose build
APP_VERSION="$(python3 -m setuptools_scm)" podman-compose build
```

(`python3 -m setuptools_scm` requires `pip install setuptools_scm` and a full
clone with tags.) CI passes this automatically when publishing images.

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

The compose file loads `.env` automatically if it exists (it is optional).

**Required Variables:**
- `WRITING_ASSISTANT_SECRET`: JWT secret key (generate with `secrets.token_urlsafe(32)`)

**Optional Variables:**
- `WRITING_ASSISTANT_HOST`: Server bind address (default: `0.0.0.0`)
- `WRITING_ASSISTANT_PORT`: Server port (default: `8001`)
- `WRITING_ASSISTANT_DB_PATH`: Database file path (default: `/app/data/writing_assistant.db`)
- `OPENAI_API_KEY`: OpenAI API key for GPT models
- `OPENAI_BASE_URL`: Alternate OpenAI-compatible endpoint (optional)
- `ANTHROPIC_API_KEY`: Anthropic API key for Claude models
- `ANTHROPIC_BASE_URL`: Alternate Anthropic-compatible endpoint (optional)
- `TALKPIPE_OLLAMA_SERVER_URL`: Ollama server URL (default: `http://localhost:11434`)
- `ALLOW_CUSTOM_ENV_VARS`: Set to `false` to prevent users from configuring connection settings (Server URL, API Key, environment variables) through the UI

**Reaching services on the host:** inside the container, `localhost` is the
container itself. The compose file maps `host.containers.internal` to the
host gateway, so an Ollama server running on the host machine is reachable
as `TALKPIPE_OLLAMA_SERVER_URL=http://host.containers.internal:11434`. See
[Connecting the Container to an LLM](#connecting-the-container-to-an-llm)
for details and the standalone `podman run` equivalent.

### Compose Services

**Production Service:**
```bash
podman-compose up -d writing-assistant
```
- Production-optimized image
- Persistent database volume
- Auto-restart on failure

**Development Service:**
```bash
podman-compose --profile dev up writing-assistant-dev
```
- Development build with all tools
- Live code reload
- Mounts source code directory

## Data Persistence

### Database Location

The SQLite database is stored in a named volume:
- Production: `writing_assistant_db` → `/app/data/writing_assistant.db`
- Development: `writing_assistant_dev_db` → `/app/data/writing_assistant.db`

> **Volume name prefix:** compose prefixes volume names with the project name
> (by default the repository directory name), so the volume is actually
> created as `talkpipe-writing-assistant_writing_assistant_db`. Check the
> real name with `podman volume ls` before running the commands below —
> using the unprefixed name silently creates a **new empty volume** instead
> of touching your data.

### Backup and Restore

**Backup:**
```bash
# Create backup directory
mkdir -p backups

# Backup database from running container
podman-compose exec writing-assistant cat /app/data/writing_assistant.db > backups/db-$(date +%Y%m%d).db

# Or copy from volume (confirm the volume name with `podman volume ls`)
podman run --rm \
  -v talkpipe-writing-assistant_writing_assistant_db:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /data/writing_assistant.db /backup/db-$(date +%Y%m%d).db
```

**Restore:**
```bash
# Stop the container
podman-compose down

# Restore from backup (confirm the volume name with `podman volume ls`)
podman run --rm \
  -v talkpipe-writing-assistant_writing_assistant_db:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /backup/db-20251012.db /data/writing_assistant.db

# Start the container
podman-compose up -d
```

## User Management

### Create First Admin User

```bash
# Using the console script (recommended)
podman-compose exec writing-assistant writing-assistant-create-superuser

# Or using Python module syntax
podman-compose exec writing-assistant python -m writing_assistant.create_superuser
```

### Manage Users via Admin Tool

```bash
# List all users
podman-compose exec writing-assistant writing-assistant-admin list

# Show detailed user information
podman-compose exec writing-assistant writing-assistant-admin info user@example.com

# Delete a user
podman-compose exec writing-assistant writing-assistant-admin delete user@example.com

# Reset password
podman-compose exec writing-assistant writing-assistant-admin reset-password user@example.com

# Toggle user active/inactive status
podman-compose exec writing-assistant writing-assistant-admin toggle-active user@example.com

# Make user a superuser
podman-compose exec writing-assistant writing-assistant-admin make-superuser user@example.com

# Show help
podman-compose exec writing-assistant writing-assistant-admin help
```

> **Dev container:** the development service (`writing-assistant-dev`) mounts
> the source tree over `/app` and does not have the console scripts on its
> `PATH`. Inside that container use the module form instead:
> `podman-compose exec writing-assistant-dev python -m writing_assistant.admin_users list`
> and `... python -m writing_assistant.create_superuser`.

### Direct Database Access

```bash
# SQLite CLI
podman-compose exec writing-assistant sqlite3 /app/data/writing_assistant.db

# List users
sqlite> SELECT id, email, is_active, is_superuser FROM users;

# Exit
sqlite> .quit
```

## Security Best Practices

### 1. Change Default Secret

**Never use the default secret in production!** Generate a strong random secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it in `.env`:
```
WRITING_ASSISTANT_SECRET=your-generated-secret-here
```

### 2. Protect Database Volume

The database volume contains all user data. Ensure:
- Regular backups
- Proper host filesystem permissions
- Encrypted filesystem (if required by compliance)

### 3. Use HTTPS in Production

Deploy behind a reverse proxy (nginx, traefik) with SSL:

```yaml
# Example nginx config
server {
    listen 443 ssl;
    server_name writing.example.com;

    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Disable Custom Environment Variables

For multi-user deployments, disable browser-based env vars by adding to `.env`:

```
ALLOW_CUSTOM_ENV_VARS=false
```

Or add to docker-compose.yml:
```yaml
command: ["python", "-m", "writing_assistant.app.server", "--disable-custom-env-vars"]
```

### 5. Regular Updates

Keep the container updated:
```bash
git pull
podman-compose build
podman-compose up -d
```

## Monitoring and Logs

### View Logs

```bash
# Follow logs
podman-compose logs -f writing-assistant

# Last 100 lines
podman-compose logs --tail=100 writing-assistant

# Logs for specific time range
podman-compose logs --since "2025-10-12T00:00:00" writing-assistant
```

### Health Check

The container includes a health check:
```bash
# Check container health
podman-compose ps

# Manual health check
podman-compose exec writing-assistant python -c "import writing_assistant; print('OK')"
```

### Resource Usage

```bash
# Container stats
podman stats writing-assistant

# Disk usage
podman system df -v
```

## Troubleshooting

### The App Runs but AI Generation Fails

Use **Settings → AI Settings → Test Connection** first — it reports the
actual failure (missing key, unreachable server, model not pulled) instead
of a generic error. The most common cause when running in a container is an
Ollama URL pointing at `localhost`, which is the container itself; see
[Connecting the Container to an LLM](#connecting-the-container-to-an-llm).

### Wrong or Missing Service Name

`podman-compose up <name>` with a service that is not in docker-compose.yml
prints `missing services [<name>]` and does nothing. The services are
`writing-assistant` (production) and `writing-assistant-dev` (development,
behind the `dev` profile).

### Container Won't Start

```bash
# Check logs
podman-compose logs writing-assistant

# Verify database permissions
podman-compose exec writing-assistant ls -la /app/data

# Reinitialize database
podman-compose exec writing-assistant python -m writing_assistant.app.server --init-db
```

### Database Locked Errors

SQLite doesn't handle concurrent writes well. If you see "database is locked":
```bash
# Stop any background admin commands
# Restart container
podman-compose restart writing-assistant
```

### Port Already in Use

Rootless Podman reports this as
`rootlessport listen tcp 0.0.0.0:8001: bind: address already in use`.

```bash
# Check what's using port 8001
sudo lsof -i :8001

# Or change port in docker-compose.yml
ports:
  - "8002:8001"  # Host:Container
```

### Permission Denied

```bash
# Fix volume permissions (confirm the volume name with `podman volume ls`;
# WARNING: removing the volume deletes all user data)
podman-compose down
podman volume rm talkpipe-writing-assistant_writing_assistant_db
podman-compose up -d
```

## Upgrading

### From Single-User to Multi-User

If you have an existing single-user deployment:

1. **Backup your data:**
   ```bash
   podman-compose down
   cp -r ./documents ~/backup-documents
   ```

2. **Pull latest code:**
   ```bash
   git pull origin main
   ```

3. **Rebuild:**
   ```bash
   podman-compose build
   ```

4. **Start and create admin:**
   ```bash
   podman-compose up -d
   podman-compose exec writing-assistant writing-assistant-create-superuser
   ```

Note: Old file-based documents are not automatically migrated. Users must re-create or import them.

## Production Deployment Checklist

- [ ] Generate and set strong `WRITING_ASSISTANT_SECRET`
- [ ] Configure SSL/TLS with reverse proxy
- [ ] Set up regular database backups (cron job)
- [ ] Configure firewall rules
- [ ] Enable container logging to external service (e.g., Splunk, ELK)
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Document admin procedures
- [ ] Test disaster recovery process
- [ ] Configure resource limits in docker-compose.yml
- [ ] Set up automated updates (e.g., Watchtower)
- [ ] Review and apply security updates regularly

## Support and Documentation

- **Full README**: See README.md for application features
- **Admin Guide**: See ADMIN_GUIDE.md for user management
- **API Documentation**: Access at `http://localhost:8001/docs` when running

## Example Production docker-compose.yml

```yaml
version: '3.8'

services:
  writing-assistant:
    image: writing-assistant:latest
    container_name: writing-assistant
    restart: always
    ports:
      - "127.0.0.1:8001:8001"  # Only localhost access
    volumes:
      - writing_assistant_db:/app/data
    environment:
      - WRITING_ASSISTANT_HOST=0.0.0.0
      - WRITING_ASSISTANT_PORT=8001
      - WRITING_ASSISTANT_DB_PATH=/app/data/writing_assistant.db
      - WRITING_ASSISTANT_SECRET=${WRITING_ASSISTANT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
    networks:
      - writing-assistant-network

  nginx:
    image: nginx:alpine
    container_name: writing-assistant-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - writing-assistant
    networks:
      - writing-assistant-network

volumes:
  writing_assistant_db:
    driver: local

networks:
  writing-assistant-network:
    driver: bridge
```
