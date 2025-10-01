<center><img src="docs/logo.png" width=400></center>

# TalkPipe Writing Assistant

An AI-powered writing assistant that transforms how you create structured documents. This application combines intelligent content generation with intuitive document management, enabling writers to craft professional documents with contextually-aware AI assistance that understands your style, audience, and objectives.

Built on the [TalkPipe framework](https://github.com/sandialabs/talkpipe), this tool helps you:

- **Break writer's block**: Generate initial drafts and ideas for any section
- **Maintain consistency**: AI understands your document's context, style, and tone across all sections
- **Iterate quickly**: Multiple generation modes (rewrite, improve, proofread, ideas) let you refine content efficiently
- **Stay organized**: Structure documents into sections with main points and supporting text
- **Work offline**: Use local LLMs via Ollama or cloud-based models via OpenAI

<center><img src="docs/screenshot.png" width=80%></center>

## Features

- **Structured Document Creation**: Organize your writing into sections with main points and user text
- **AI-Powered Generation**: Generate contextually-aware paragraph content using advanced language models
- **Multiple Generation Modes**:
  - **Rewrite**: Complete rewrite with new ideas and improved clarity
  - **Improve**: Polish existing text while maintaining structure
  - **Proofread**: Fix grammar and spelling errors only
  - **Ideas**: Get specific suggestions for enhancement
- **Real-time Editing**: Dynamic web interface for seamless writing and editing
- **Document Management**: Save, load, and manage multiple documents with snapshots
- **Customizable Metadata**: Configure writing style, tone, audience, and generation parameters
- **Flexible AI Backend**: Support for OpenAI (GPT-4, GPT-5) and Ollama (llama3, mistral, etc.)
- **Async Processing**: Efficient queuing system for AI generation requests

## Installation

### Prerequisites

- Python 3.11 or higher
- An AI backend: either OpenAI API access or Ollama installed locally

### Using pip

```bash
pip install talkpipe-writing-assistant
```

### From source

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

### Using Docker

```bash
# Production deployment
docker-compose up talkpipe-writing-assistant

# Development with live reload
docker-compose --profile dev up talkpipe-writing-assistant-dev
```

## Configuration

### Configuring OpenAI

To use OpenAI models (GPT-4, GPT-5, etc.):

#### Option 1: Server-Level Configuration (Recommended for single-user)

1. Obtain an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Set your API key as an environment variable:
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

3. Configure in the application:
   - In the web interface, click **Settings** → **AI Settings** tab
   - Set the **AI Source** to `openai`
   - Set the **Model** to your desired model (e.g., `gpt-4`, `gpt-4-turbo`, `gpt-5`)

#### Option 2: Browser-Based Configuration (Multi-user or temporary credentials)

1. Obtain an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. In the web interface:
   - Click **Settings** → **AI Settings** tab
   - Under **Environment Variables**, click **+ Add Environment Variable**
   - Set `OPENAI_API_KEY` as the variable name
   - Paste your API key as the value
   - Click **Save AI Settings**

3. Configure AI settings:
   - Set the **AI Source** to `openai`
   - Set the **Model** to your desired model

**Environment Variables in Browser:**
- Stored securely in your browser's localStorage (never in document files)
- Apply to all documents automatically
- Can be disabled server-side with `--disable-custom-env-vars` flag for security

**Security Note:**
- For shared/multi-user deployments, use server-level configuration only
- Disable browser-based env vars with: `writing-assistant --disable-custom-env-vars`
- This prevents users from injecting arbitrary credentials

**Cost Considerations:**
- OpenAI charges per token (input + output)
- Check current pricing at [OpenAI Pricing](https://openai.com/api/pricing/)
- Typical paragraph generation uses 200-1000 tokens

### Configuring Ollama

To use local LLMs via Ollama (free, runs on your computer):

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model (first time only):
   ```bash
   ollama pull llama3.1:8b
   ```
3. Start Ollama (if not already running):
   ```bash
   ollama serve
   ```
4. **Configure in the application**:
   - In the web interface, click **Settings** → **AI Settings** tab
   - Set the **AI Source** to `ollama`
   - Set the **Model** to your chosen model (e.g., `llama3.1:8b`, `mistral:7b`)

**No API keys required** - Ollama runs entirely on your local machine!

### TalkPipe Configuration

The application uses [TalkPipe](https://github.com/sandialabs/talkpipe) for AI integration. TalkPipe automatically detects your configuration from environment variables:

## Usage

### Starting the Server

```bash
# Default: http://localhost:8001
writing-assistant

# Custom port
WRITING_ASSISTANT_PORT=8080 writing-assistant

# Enable auto-reload for development
WRITING_ASSISTANT_RELOAD=true writing-assistant

# With custom authentication token
writing-assistant --auth-token YOUR_SECURE_TOKEN_HERE
```

When the server starts, it will display:
- The URL to access the application (including the authentication token)
- The authentication token itself

**Authentication:** The application uses token-based authentication. A unique token is auto-generated on startup, or you can provide your own using `--auth-token`. You'll need to include this token in the URL query string: `http://localhost:8001/?token=YOUR_TOKEN`

### Environment Variables

Configure the application with these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `WRITING_ASSISTANT_HOST` | Server host address | `localhost` |
| `WRITING_ASSISTANT_PORT` | Server port number | `8001` |
| `WRITING_ASSISTANT_RELOAD` | Enable auto-reload (development) | `false` |
| `OPENAI_API_KEY` | OpenAI API key for OpenAI models | (none) |
| `OLLAMA_BASE_URL` | Ollama server URL for local models | `http://localhost:11434` |

### Command-Line Options

```bash
writing-assistant [OPTIONS]

Options:
  --host HOST                    Host to bind to (default: localhost)
  --port PORT                    Port to bind to (default: 8001)
  --reload                       Enable auto-reload for development
  --auth-token TOKEN             Custom authentication token (default: auto-generated UUID)
  --disable-custom-env-vars      Disable custom environment variables from UI (security feature)
```

**Security Options:**
- `--disable-custom-env-vars`: Prevents users from configuring environment variables through the browser interface
  - Use this for shared deployments or when you want centralized credential management
  - Environment variables must be set at the server level (via shell environment)
  - The Environment Variables section will be hidden in the UI

### Using the Web Interface

1. **Start the server**:
   ```bash
   writing-assistant
   ```
   The server will display a URL with the authentication token, for example:
   ```
   📝 Access your writing assistant at: http://localhost:8001/?token=abc123...
   ```

2. **Open your browser** to the URL provided (with the token parameter)

3. **Configure document metadata**:
   - AI Source: `openai` or `ollama`
   - Model: e.g., `gpt-4-turbo` or `llama3.1:8b`
   - Writing style: formal, casual, technical, etc.
   - Target audience: general public, experts, students, etc.
   - Tone: neutral, persuasive, informative, etc.
   - Word limit: approximate words per paragraph

4. **Create your document**:
   - Set the document title
   - Add sections with "Add Section"
   - For each section:
     - Enter the main point
     - Add your draft text (optional)
     - Click "Generate" to create AI-generated content
     - Use different generation modes as needed

5. **Generation modes**:
   - **Rewrite**: Complete rewrite with new ideas
   - **Improve**: Polish existing text
   - **Proofread**: Fix errors only
   - **Ideas**: Get suggestions for improvement

6. **Save your work**:
   - Click "Save Document" to persist to disk
   - Load previous documents from the dropdown
   - Create snapshots to save versions
   - Revert to previous snapshots as needed

### Document Storage

Documents are saved to `~/.writing_assistant/documents/` as JSON files with:
- Document metadata and settings
- All sections with their content
- Snapshot history for version control

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

### AI Integration

The application uses TalkPipe to abstract AI provider details:
- Supports multiple LLM sources (OpenAI, Ollama, etc.)
- Context-aware prompting includes previous/next paragraphs for coherence
- Thread-safe generation with request queuing
- Multiple generation modes with specialized system prompts

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository at [github.com/sandialabs/talkpipe-writing-assistant](https://github.com/sandialabs/talkpipe-writing-assistant)
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `pytest`
6. Run code quality checks: `black src/ tests/ && flake8 src/ tests/`
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## Troubleshooting

### OpenAI Issues

**"Authentication error"**
- Verify your API key is set: `echo $OPENAI_API_KEY`
- Check the key is valid at [OpenAI Platform](https://platform.openai.com/api-keys)

**"Rate limit exceeded"**
- You've exceeded your OpenAI usage quota
- Check your usage at [OpenAI Usage](https://platform.openai.com/usage)

### Ollama Issues

**"Connection refused"**
- Check Ollama is running: `ollama list`
- Start Ollama if needed: `ollama serve`

**"Model not found"**
- Pull the model: `ollama pull llama3.1:8b`
- Verify available models: `ollama list`

**"Out of memory"**
- Use a smaller model (e.g., `mistral:7b` instead of `llama3.1:70b`)
- Close other applications to free RAM

### Application Issues

**"Port already in use"**
- Change the port: `WRITING_ASSISTANT_PORT=8080 writing-assistant`
- Or kill the process using the port

**"Cannot save document"**
- Check write permissions to `~/.writing_assistant/documents/`
- Create the directory if needed: `mkdir -p ~/.writing_assistant/documents/`

## Project Links

- **Homepage**: [github.com/sandialabs/talkpipe-writing-assistant](https://github.com/sandialabs/talkpipe-writing-assistant)
- **Repository**: [github.com/sandialabs/talkpipe-writing-assistant](https://github.com/sandialabs/talkpipe-writing-assistant)
- **Documentation**: [github.com/sandialabs/talkpipe-writing-assistant#readme](https://github.com/sandialabs/talkpipe-writing-assistant#readme)
- **Bug Tracker**: [github.com/sandialabs/talkpipe-writing-assistant/issues](https://github.com/sandialabs/talkpipe-writing-assistant/issues)

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](https://github.com/sandialabs/talkpipe-writing-assistant/blob/master/LICENSE) file for details.

## Security

For security issues, please see our [Security Policy](https://github.com/sandialabs/talkpipe-writing-assistant/blob/master/.github/SECURITY.md).

## Acknowledgments

Built with [TalkPipe](https://github.com/sandialabs/talkpipe), a flexible framework for AI pipeline construction developed at Sandia National Laboratories.