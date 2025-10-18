# Docker Deployment Guide

This guide explains how to deploy the Writing Assistant using Docker and Docker Compose.

## Quick Start

### 1. Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/writing-assistant.git
cd writing-assistant

# Generate a secure secret
python -c "import secrets; print(secrets.token_urlsafe(32))" > .secret

# Create environment file
cat > .env << EOF
WRITING_ASSISTANT_SECRET=$(cat .secret)
OPENAI_API_KEY=your-key-here  # Optional
EOF

# Start the production service
docker-compose up -d writing-assistant

# Check logs
docker-compose logs -f writing-assistant

# Create the first admin user (in another terminal)
docker-compose exec -it writing-assistant writing-assistant-create-superuser
```

Access the application at: `http://localhost:8001`

### 2. Using Docker Directly

```bash
# Build the image
docker build -t writing-assistant .

# Run the container
docker run -d \
  --name writing-assistant \
  -p 8001:8001 \
  -v writing-assistant-db:/app/data \
  -e WRITING_ASSISTANT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
  writing-assistant

# Create admin user
docker exec -it writing-assistant writing-assistant-create-superuser
```

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

**Required Variables:**
- `WRITING_ASSISTANT_SECRET`: JWT secret key (generate with `secrets.token_urlsafe(32)`)

**Optional Variables:**
- `WRITING_ASSISTANT_HOST`: Server bind address (default: `0.0.0.0`)
- `WRITING_ASSISTANT_PORT`: Server port (default: `8001`)
- `WRITING_ASSISTANT_DB_PATH`: Database file path (default: `/app/data/writing_assistant.db`)
- `OPENAI_API_KEY`: OpenAI API key for GPT models
- `OLLAMA_BASE_URL`: Ollama server URL (default: `http://localhost:11434`)

### Docker Compose Services

**Production Service:**
```bash
docker-compose up -d writing-assistant
```
- Production-optimized image
- Persistent database volume
- Auto-restart on failure

**Development Service:**
```bash
docker-compose --profile dev up writing-assistant-dev
```
- Development build with all tools
- Live code reload
- Mounts source code directory

## Data Persistence

### Database Location

The SQLite database is stored in a Docker volume:
- Production: `writing_assistant_db` → `/app/data/writing_assistant.db`
- Development: `writing_assistant_dev_db` → `/app/data/writing_assistant.db`

### Backup and Restore

**Backup:**
```bash
# Create backup directory
mkdir -p backups

# Backup database from running container
docker-compose exec writing-assistant cat /app/data/writing_assistant.db > backups/db-$(date +%Y%m%d).db

# Or copy from volume
docker run --rm \
  -v writing_assistant_db:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /data/writing_assistant.db /backup/db-$(date +%Y%m%d).db
```

**Restore:**
```bash
# Stop the container
docker-compose down

# Restore from backup
docker run --rm \
  -v writing_assistant_db:/data \
  -v $(pwd)/backups:/backup \
  alpine cp /backup/db-20251012.db /data/writing_assistant.db

# Start the container
docker-compose up -d
```

## User Management

### Create First Admin User

```bash
# Using the console script (recommended)
docker-compose exec -it writing-assistant writing-assistant-create-superuser

# Or using Python module syntax
docker-compose exec -it writing-assistant python -m writing_assistant.create_superuser
```

### Manage Users via Admin Tool

```bash
# List all users
docker-compose exec writing-assistant writing-assistant-admin list

# Show detailed user information
docker-compose exec writing-assistant writing-assistant-admin info user@example.com

# Delete a user
docker-compose exec -it writing-assistant writing-assistant-admin delete user@example.com

# Reset password
docker-compose exec -it writing-assistant writing-assistant-admin reset-password user@example.com

# Toggle user active/inactive status
docker-compose exec writing-assistant writing-assistant-admin toggle-active user@example.com

# Make user a superuser
docker-compose exec writing-assistant writing-assistant-admin make-superuser user@example.com

# Show help
docker-compose exec writing-assistant writing-assistant-admin help
```

### Direct Database Access

```bash
# SQLite CLI
docker-compose exec writing-assistant sqlite3 /app/data/writing_assistant.db

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

For multi-user deployments, disable browser-based env vars:

```bash
docker-compose exec writing-assistant \
  python -m writing_assistant.app.server --disable-custom-env-vars
```

Or add to docker-compose.yml:
```yaml
command: ["python", "-m", "writing_assistant.app.server", "--disable-custom-env-vars"]
```

### 5. Regular Updates

Keep the container updated:
```bash
git pull
docker-compose build
docker-compose up -d
```

## Monitoring and Logs

### View Logs

```bash
# Follow logs
docker-compose logs -f writing-assistant

# Last 100 lines
docker-compose logs --tail=100 writing-assistant

# Logs for specific time range
docker-compose logs --since "2025-10-12T00:00:00" writing-assistant
```

### Health Check

The container includes a health check:
```bash
# Check container health
docker-compose ps

# Manual health check
docker-compose exec writing-assistant python -c "import writing_assistant; print('OK')"
```

### Resource Usage

```bash
# Container stats
docker stats writing-assistant

# Disk usage
docker system df -v
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs writing-assistant

# Verify database permissions
docker-compose exec writing-assistant ls -la /app/data

# Reinitialize database
docker-compose exec writing-assistant python -m writing_assistant.app.server --init-db
```

### Numba Caching Errors

If you see errors like `RuntimeError: cannot cache function 'rdist': no locator available`, this is resolved in the current Dockerfile by setting `NUMBA_CACHE_DIR=/tmp/numba_cache`. If using an older version:

```bash
# Rebuild with latest Dockerfile
docker-compose build --no-cache writing-assistant
docker-compose up -d
```

### Database Locked Errors

SQLite doesn't handle concurrent writes well. If you see "database is locked":
```bash
# Stop any background admin commands
# Restart container
docker-compose restart writing-assistant
```

### Port Already in Use

```bash
# Check what's using port 8001
sudo lsof -i :8001

# Or change port in docker-compose.yml
ports:
  - "8002:8001"  # Host:Container
```

### Permission Denied

```bash
# Fix volume permissions
docker-compose down
docker volume rm writing_assistant_db
docker-compose up -d
```

## Upgrading

### From Single-User to Multi-User

If you have an existing single-user deployment:

1. **Backup your data:**
   ```bash
   docker-compose down
   cp -r ./documents ~/backup-documents
   ```

2. **Pull latest code:**
   ```bash
   git pull origin main
   ```

3. **Rebuild:**
   ```bash
   docker-compose build
   ```

4. **Start and create admin:**
   ```bash
   docker-compose up -d
   docker-compose exec -it writing-assistant writing-assistant-create-superuser
   ```

Note: Old file-based documents are not automatically migrated. Users must re-create or import them.

## Production Deployment Checklist

- [ ] Generate and set strong `WRITING_ASSISTANT_SECRET`
- [ ] Configure SSL/TLS with reverse proxy
- [ ] Set up regular database backups (cron job)
- [ ] Configure firewall rules
- [ ] Enable Docker logging to external service (e.g., Splunk, ELK)
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
