<center><img src="docs/logo.png" width=400></center>

# 

An AI-powered writing assistant that transforms how you create structured documents. Built on the TalkPipe framework, this application combines intelligent content generation with intuitive document management, enabling writers to craft professional documents with contextually-aware AI assistance that understands your style, audience, and objectives.

<center><img src="docs/screenshot.png" width=500></center>

## Features

- **Structured Document Creation**: Organize your writing into sections with main points and user text
- **AI-Powered Generation**: Generate contextually-aware paragraph content using advanced language models
- **Real-time Editing**: Dynamic web interface for seamless writing and editing
- **Document Management**: Save, load, and manage multiple documents
- **Customizable Metadata**: Configure writing style, tone, audience, and generation parameters
- **Async Processing**: Efficient queuing system for AI generation requests

## Installation

### Using pip

```bash
pip install writing-assistant
```

### From source

```bash
git clone https://github.com/sandialabs/talkpipe-writing-assistant.git
cd writing-assistant
pip install -e .
```

### Using Docker

```bash
# Production deployment
docker-compose up talkpipe-writing-assistant

# Development with live reload
docker-compose --profile dev up talkpipe-writing-assistant-dev
```

## Usage

### Command Line

Start the writing assistant server:

```bash
writing-assistant
```

The application will be available at http://localhost:8001

### Configuration

The application can be configured using environment variables:

- `WRITING_ASSISTANT_HOST`: Server host (default: localhost)
- `WRITING_ASSISTANT_PORT`: Server port (default: 8001)
- `WRITING_ASSISTANT_RELOAD`: Enable auto-reload for development (default: false)

### Web Interface

1. Open http://localhost:8001 in your browser
2. Configure document metadata (writing style, audience, tone, etc.)
3. Add sections with main points and user text
4. Generate AI-powered content for each section
5. Save and load documents as needed

## Development

### Setup

```bash
git clone https://github.com/sandialabs/writing-assistant.git
cd writing-assistant
pip install -e .[dev]
```

### Running Tests

```bash
pytest
# With coverage
pytest --cov=src --cov-report=html
```

### Code Formatting

```bash
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

### Type Checking

```bash
mypy src/
```

### Security Scanning

```bash
bandit -r src/
safety check
```

## Architecture

The application consists of several key components:

- **Core Module** (`writing_assistant.core`): Data models and AI generation logic
- **Web Application** (`writing_assistant.app`): FastAPI-based web interface
- **Document Management**: JSON-based document persistence
- **AI Integration**: TalkPipe framework for language model interactions

### Key Classes

- `Metadata`: Configuration for writing style, audience, and generation parameters
- `Section`: Individual document sections with async text generation
- `Document`: Complete document with sections and metadata

## Dependencies

- **TalkPipe**: AI pipeline framework for language model integration
- **FastAPI**: Modern web framework for the API
- **Uvicorn**: ASGI server for running the application
- **Jinja2**: Template engine for the web interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite and ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.

## Security

For security issues, please see our [Security Policy](.github/SECURITY.md).