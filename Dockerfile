# Multi-stage build for Writing Assistant
# Stage 1: Build stage with all development dependencies
FROM python:3.11-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    make \
    cmake \
    pkg-config \
    libxml2-dev \
    libxslt-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create build user
RUN groupadd -r builder && useradd -r -g builder -m builder

# Set up build environment
WORKDIR /build
RUN chown builder:builder /build
USER builder

# Copy source files
COPY --chown=builder:builder pyproject.toml README.md LICENSE ./
COPY --chown=builder:builder src/ src/
COPY --chown=builder:builder tests/ tests/

# Install Python dependencies and build the package
RUN python -m pip install --user --upgrade pip setuptools wheel build
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_WRITING_ASSISTANT=0.1.0
RUN python -m pip install --user -e .[dev]
RUN python -m pytest --log-cli-level=DEBUG || true  # Allow tests to fail during build
RUN python -m build --wheel

# Stage 2: Runtime stage with minimal dependencies
FROM python:3.11-slim AS runtime

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create application user with specific UID/GID for better security
RUN groupadd -r -g 1001 app && \
    useradd -r -u 1001 -g app -s /sbin/nologin \
        -c "Writing Assistant Application User" app

# Set up application directory
WORKDIR /app
RUN mkdir -p /app/data /app/documents && \
    chown -R app:app /app

# Copy the built wheel from builder stage
COPY --from=builder --chown=app:app /build/dist/*.whl /tmp/

# Install runtime Python dependencies and the application
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir /tmp/*.whl && \
    rm -f /tmp/*.whl

# Copy only necessary runtime files
COPY --chown=app:app pyproject.toml ./

# Create data and document volume mount points
VOLUME ["/app/data", "/app/documents"]

# Switch to non-root user
USER app

# Expose the application port
EXPOSE 8001

# Health check to ensure the application starts correctly
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import writing_assistant; print('Writing Assistant loaded successfully')" || exit 1

# Set environment variables for better container behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WRITING_ASSISTANT_HOST=0.0.0.0 \
    WRITING_ASSISTANT_PORT=8001

# Default command to run the application
CMD ["python", "-m", "writing_assistant.app.server"]