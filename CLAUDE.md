# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Guidance
Do not automatically agree.  Question assumptions and point out weaknesses in logic or inconsistences with the
  rest of the codebase.
After implementing a new feature, update CHANGELOG.md.  
After making a minor change to an existing feature,  check if the unreleased section of the changelog already 
    mentions the feature. If so, update that changelog entry.  If not, write a new entry in the changelog.
When making a change, write a unit test that fails without the change, verify that the unit test fails, 
    make the change and then verity that the unit test now passes.  Notify the user if it is not reasonable 
    to write the unit test. 
User interfaces should be visually appealing and maintain consistency with each other.

## Development Commands

### Installation
```bash
# Development installation
pip install -e .[dev]

# Production installation
pip install writing-assistant
```

### Running the Application

**Multi-User Mode (Default):**
```bash
# Using the CLI command
writing-assistant

# Or directly with Python
python -m writing_assistant.app.server

# Development with auto-reload
WRITING_ASSISTANT_RELOAD=true writing-assistant

# Initialize database manually (optional, done automatically on startup)
writing-assistant --init-db
```

**Important:** The application now uses FastAPI Users for multi-user authentication. Users must register and login to use the application.

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py
```

**Note:** Tests now use FastAPI Users authentication with test user fixtures. See the test fixtures in `tests/conftest.py` for details on test user setup.

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
safety check
```

### Docker Commands
```bash
# Build and run production container
docker-compose up writing-assistant

# Run development container with live reload
docker-compose --profile dev up writing-assistant-dev

# Build container manually
docker build -t writing-assistant .
```

## Architecture Overview

This is a FastAPI-based writing assistant application that helps users create structured documents with AI-generated content. The application uses the TalkPipe framework for AI text generation, FastAPI Users for multi-user authentication, and SQLAlchemy for database management. It follows modern Python packaging standards.

### Multi-User Authentication

The application uses **FastAPI Users** (v13+) for complete user management:

**Authentication Features:**
- User registration with email and password
- JWT-based authentication (Bearer tokens)
- Password reset functionality
- Email verification support
- User profile management

**API Endpoints:**
- `POST /auth/register` - Register a new user
- `POST /auth/jwt/login` - Login and get JWT token
- `POST /auth/jwt/logout` - Logout (invalidate token)
- `POST /auth/forgot-password` - Request password reset
- `POST /auth/reset-password` - Reset password with token
- `GET /users/me` - Get current user profile
- `PATCH /users/me` - Update current user profile

**Database:**
- SQLite database stored in `~/.writing_assistant/writing_assistant.db`
- User accounts with hashed passwords (bcrypt)
- Documents scoped to individual users
- Document snapshots for version history

**Security:**
- JWT tokens with 7-day expiration
- Passwords hashed with bcrypt
- All document endpoints require authentication
- Users can only access their own documents
- Secret key configurable via `WRITING_ASSISTANT_SECRET` environment variable

**Usage Example:**
```bash
# 1. Start the server
writing-assistant

# 2. Register a new user (using curl)
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'

# 3. Login to get JWT token
curl -X POST http://localhost:8001/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword"

# 4. Use the token in subsequent requests
curl -X GET http://localhost:8001/documents/list \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

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
    ├── models.py        # SQLAlchemy database models (User, Document, DocumentSnapshot)
    ├── schemas.py       # Pydantic schemas for API validation
    ├── database.py      # Database configuration and session management
    ├── auth.py          # FastAPI Users authentication setup
    ├── static/          # CSS and JavaScript assets
    └── templates/       # Jinja2 HTML templates
```

### Core Components

**src/writing_assistant/app/main.py**: Contains the main FastAPI application with:
- FastAPI Users authentication routers (register, login, password reset, etc.)
- REST API endpoints for CRUD operations on documents
- Document persistence using SQLAlchemy database
- User-scoped document access with authentication required

**src/writing_assistant/app/models.py**: SQLAlchemy database models:
- `User` model: Extends FastAPI Users base with email, hashed password, and timestamps
- `Document` model: Stores document content (JSON) with user foreign key
- `DocumentSnapshot` model: Version history for documents

**src/writing_assistant/app/database.py**: Database configuration:
- Async SQLAlchemy engine and session management
- Database URL configuration (SQLite in `~/.writing_assistant/`)
- Session and user database dependencies

**src/writing_assistant/app/auth.py**: Authentication setup:
- `UserManager` class for user lifecycle events
- JWT authentication backend with Bearer transport
- `current_active_user` dependency for protected endpoints

**src/writing_assistant/app/schemas.py**: Pydantic schemas:
- User schemas (UserRead, UserCreate, UserUpdate)
- Document schemas (DocumentCreate, DocumentRead, DocumentList)
- Snapshot schemas (SnapshotCreate, SnapshotRead)

**src/writing_assistant/core/callbacks.py**: AI text generation functionality:
- Uses TalkPipe framework for LLM integration
- `new_paragraph()` function generates text based on context and metadata
- Currently hardcoded to use OpenAI GPT-5 model
- Thread-safe generation with locking mechanism

**src/writing_assistant/core/definitions.py**: Data models:
- `Metadata` class defining writing style, audience, tone, and generation parameters

**src/writing_assistant/app/server.py**: Application entry point:
- Configurable host, port, and reload settings via environment variables
- Database initialization on startup
- Main function for CLI command

### Key Features

- **Multi-User Authentication**: FastAPI Users with JWT-based authentication
- **User-Scoped Documents**: Each user can only access their own documents
- **Database Persistence**: SQLite database with SQLAlchemy ORM
- **Async Text Generation**: AI-powered paragraph generation using TalkPipe
- **Context-Aware Generation**: Takes into account previous/next paragraphs, document title, and metadata
- **Document Snapshots**: Version history with automatic cleanup (keep 10 most recent)
- **Web Interface**: HTML templates with JavaScript for dynamic interaction
- **Pip Installable**: Proper Python package with console scripts
- **Docker Support**: Multi-stage builds for development and production
- **CI/CD**: GitHub Actions pipeline with testing, security scanning, and container builds

### Configuration

Environment variables:
- `WRITING_ASSISTANT_HOST`: Server host (default: localhost)
- `WRITING_ASSISTANT_PORT`: Server port (default: 8001)
- `WRITING_ASSISTANT_RELOAD`: Enable auto-reload (default: false)
- `WRITING_ASSISTANT_SECRET`: Secret key for JWT tokens (default: insecure value, **must set in production**)

### Dependencies

The application depends on:
- **TalkPipe** (>=0.9.2): AI pipeline functionality
- **FastAPI[standard]** (>=0.104.1): Web framework
- **FastAPI-Users[sqlalchemy]** (>=13.0.0): User authentication and management
- **SQLAlchemy[asyncio]** (>=2.0.0): ORM and database toolkit
- **Aiosqlite** (>=0.19.0): Async SQLite driver
- **Alembic** (>=1.12.0): Database migrations
- **Uvicorn** (>=0.24.0): ASGI server
- **Jinja2** (>=3.1.2): Template engine
- **Python-multipart** (>=0.0.6): Form data handling
- **Pydantic** (>=2.0.0): Data validation

### Text Generation Pipeline

Text generation uses a sophisticated prompt template that includes:
- Document metadata (style, audience, tone, context)
- Current paragraph content and main point
- Previous and next paragraph context for coherence
- Word limits and special generation directives

The generation is queued per section to prevent overwhelming the AI service while maintaining responsiveness.

### Testing

The project includes comprehensive tests:
- **Unit tests**: Core functionality testing
- **API tests**: FastAPI endpoint testing with TestClient
- **Integration tests**: End-to-end document workflows
- **Coverage reporting**: HTML and XML coverage reports
- **Fixtures**: Reusable test data and client setup
