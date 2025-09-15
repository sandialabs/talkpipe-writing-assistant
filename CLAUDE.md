# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation
```bash
# Development installation
pip install -e .[dev]

# Production installation
pip install writing-assistant
```

### Running the Application
```bash
# Using the CLI command
writing-assistant

# Or directly with Python
python -m writing_assistant.app.server

# Development with auto-reload
WRITING_ASSISTANT_RELOAD=true writing-assistant
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py
```

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

This is a FastAPI-based writing assistant application that helps users create structured documents with AI-generated content. The application uses the TalkPipe framework for AI text generation and follows modern Python packaging standards.

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

**src/writing_assistant/app/main.py**: Contains the main FastAPI application with:
- `Document` class: Manages document structure with sections and metadata
- `Section` class: Individual document sections with async text generation and queuing system
- REST API endpoints for CRUD operations on documents and sections
- Document persistence (save/load/list/delete operations)

**src/writing_assistant/core/callbacks.py**: AI text generation functionality:
- Uses TalkPipe framework for LLM integration
- `new_paragraph()` function generates text based on context and metadata
- Currently hardcoded to use OpenAI GPT-5 model
- Thread-safe generation with locking mechanism

**src/writing_assistant/core/definitions.py**: Data models:
- `Metadata` class defining writing style, audience, tone, and generation parameters

**src/writing_assistant/app/server.py**: Application entry point:
- Configurable host, port, and reload settings via environment variables
- Main function for CLI command

### Key Features

- **Async Text Generation**: Sections use queuing system to handle multiple generation requests (max 2: current + pending)
- **Context-Aware Generation**: Takes into account previous/next paragraphs, document title, and metadata
- **Document Persistence**: Documents saved to `~/.writing_assistant/documents/` as JSON files
- **Web Interface**: HTML templates with JavaScript for dynamic interaction
- **Pip Installable**: Proper Python package with console scripts
- **Docker Support**: Multi-stage builds for development and production
- **CI/CD**: GitHub Actions pipeline with testing, security scanning, and container builds

### Configuration

Environment variables:
- `WRITING_ASSISTANT_HOST`: Server host (default: localhost)
- `WRITING_ASSISTANT_PORT`: Server port (default: 8001)
- `WRITING_ASSISTANT_RELOAD`: Enable auto-reload (default: false)

### Dependencies

The application depends on:
- **TalkPipe** (>=0.9.0a5): AI pipeline functionality
- **FastAPI[standard]** (>=0.104.1): Web framework
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