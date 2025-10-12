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

### Multi-User Research

The following is the result of doing multi-user research.  Use this background when developing multi-user code.

# Building Multi-Tenant FastAPI Applications: A Production Guide

**Schema-per-tenant with PostgreSQL emerges as the optimal architecture for most multi-tenant FastAPI applications**, balancing strong isolation, cost efficiency, and operational complexity. This approach scales to thousands of tenants while leveraging FastAPI's dependency injection system and SQLAlchemy's schema translation features. For authentication, FastAPI Users provides the most complete solution with built-in user management, while security requires defense-in-depth with application-level validation, database row-level security, and comprehensive audit logging.

The production landscape reveals no single library handles all multi-tenant concerns—success requires orchestrating FastAPI's native capabilities with strategic architectural decisions. Most critical: always derive tenant context from authenticated sessions, never trust client-provided identifiers, and implement tenant isolation at multiple layers. This guide synthesizes battle-tested patterns from production SaaS applications, OWASP security frameworks, and the FastAPI ecosystem.

## Multi-tenancy requires architectural choices at the foundation

The fundamental decision in multi-tenant architecture is how to isolate tenant data. **Three primary patterns** dominate production applications, each with distinct tradeoffs:

**Schema-per-tenant** provides the sweet spot for 100-1,000 tenants. Each tenant gets a dedicated PostgreSQL schema (like `tenant_a`, `tenant_b`) within a shared database. SQLAlchemy's `schema_translate_map` dynamically routes queries to the correct schema at runtime. This delivers strong isolation—schemas are logically separate namespaces—while maintaining centralized management. Migration complexity is moderate: you run schema updates across all tenant schemas, but this beats managing separate databases. Cost efficiency remains high since connection pooling works across tenants. The pattern excels for B2B SaaS where tenants need schema customization potential but you want operational simplicity.

**Shared database with tenant_id** scales to millions of tenants with lowest cost. All tenants share tables, with a `tenant_id` column filtering every query. Implementation is straightforward, but the risk is high: forgetting `WHERE tenant_id = X` in a single query leaks data across tenants. PostgreSQL Row-Level Security (RLS) provides crucial backup—the database enforces tenant isolation even if application code fails. This pattern suits high-volume consumer SaaS with standardized service where customization isn't required.

**Database-per-tenant** offers maximum isolation but at significant cost. Each tenant gets a completely separate database instance. This simplifies security—complete physical separation—and enables per-tenant encryption keys, custom performance tuning, and independent scaling. However, operational overhead becomes severe: schema migrations must run across hundreds of databases, connection pool requirements multiply, and costs scale linearly. Reserve this for enterprise customers with strict compliance requirements (HIPAA, FedRAMP) or when tenants pay enough to justify dedicated infrastructure.

The decision matrix crystallizes around three factors: tenant count determines operational viability (databases work for 10-50 tenants, schemas for 100-1,000s, shared tables for millions), compliance requirements dictate isolation strength needed, and budget constraints limit infrastructure investment. For most SaaS startups building multi-tenant products, **start with schema-per-tenant**—it provides room to grow while maintaining strong security boundaries.

## Tenant identification strategy shapes the entire application

How you identify which tenant a request belongs to permeates every layer of your application. **Four primary strategies** exist, each with distinct implications:

**Subdomain-based identification** (`tenant1.app.com`, `tenant2.app.com`) provides the most user-friendly experience. Users see their tenant in the URL, bookmarks work intuitively, and branding opportunities emerge. Implementation requires DNS wildcard configuration and SSL certificate management (wildcard cert or automated cert provisioning). FastAPI middleware extracts the subdomain from the `Host` header and looks up the corresponding tenant in a shared metadata table. This pattern excels for web applications where user experience matters and you can manage DNS infrastructure.

**Header-based identification** (`X-Tenant-ID: abc123`) suits API-first applications. Mobile apps and SPAs include the tenant identifier in request headers, often alongside authentication tokens. This keeps URLs clean and works well with API gateways. The downside: users never see tenant context, making debugging harder. Combine this with JWT tokens that embed `tenant_id` in claims for verification—never trust the header alone.

**Path-based identification** (`/tenant/abc123/resources`) embeds tenant context directly in URL paths. This makes tenant context explicit and requires no special infrastructure. However, it exposes tenant identifiers (security consideration), creates longer URLs, and complicates routing. Use primarily for admin interfaces or when other methods aren't viable.

**JWT claims-based** treats tenant as part of authenticated identity. The JWT token includes `tenant_id` in claims alongside user identity. Every protected endpoint extracts tenant context from the validated token. This provides **the strongest security model**—tenant context is cryptographically bound to authentication. Always use this in conjunction with other methods for verification.

Production applications typically combine multiple strategies: subdomain for user-facing web interfaces, JWT claims for API authentication, and header-based as fallback for service-to-service communication.

## FastAPI Users provides the most complete authentication foundation

The authentication landscape offers several options, but **FastAPI Users** emerges as the most comprehensive solution for production applications. Version 14+ provides ready-to-use registration, login, password reset, email verification, and OAuth social authentication. The library follows a modular architecture: `UserManager` handles user lifecycle, database adapters connect to SQLAlchemy or Beanie (MongoDB), authentication backends combine transports (Bearer/Cookie) with strategies (JWT/Database tokens), and routers provide pre-built endpoints that integrate seamlessly with OpenAPI schemas.

```python
from fastapi_users import FastAPIUsers, BaseUserManager
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
import uuid

class UserManager(BaseUserManager[User, uuid.UUID]):
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        # Custom logic after registration
        print(f"User {user.id} has registered")

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Easy integration with routes
current_active_user = fastapi_users.current_user(active=True)

@app.get("/protected")
async def protected_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}"}
```

**AuthLib** serves different needs—it's the go-to for OAuth/OIDC integration with external providers. When your application needs Google/Facebook/GitHub login or enterprise SSO via Auth0/Okta/Azure AD, AuthLib provides comprehensive OAuth 2.0 and OpenID Connect support. However, it doesn't include user management, requiring you to build registration and profile management separately.

**Native FastAPI security** with `OAuth2PasswordBearer` and manual JWT implementation offers maximum control and minimal dependencies. For microservices or API-only applications where you need lightweight token validation without user management overhead, building directly on FastAPI's security primitives makes sense. The tradeoff is writing more boilerplate for password hashing, token generation, and refresh logic.

In multi-tenant contexts, authentication integrates with tenant identification. The recommended pattern embeds `tenant_id` in JWT claims alongside user identity. Every protected endpoint validates both authentication and tenant context:

```python
from fastapi import Depends, HTTPException
from jose import jwt, JWTError

async def get_current_user_and_tenant(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        
        if not user_id or not tenant_id:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        return {"user_id": user_id, "tenant_id": tenant_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.get("/tenant/resources")
async def get_resources(
    auth: dict = Depends(get_current_user_and_tenant),
    db: Session = Depends(get_db)
):
    # Tenant context automatically enforced
    resources = db.query(Resource).filter(
        Resource.tenant_id == auth["tenant_id"]
    ).all()
    return resources
```

The critical insight: **never trust client-provided tenant identifiers**. Always derive tenant context from the authenticated session. An attacker who can manipulate tenant IDs bypasses all isolation.

## Storage isolation requires defense in depth across application and database layers

Effective storage isolation implements multiple security boundaries. **Application-level filtering** forms the first line of defense. Every database query includes tenant context, typically through dependency injection that automatically scopes queries:

```python
from contextvars import ContextVar
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# Context variable for async-safe tenant tracking
tenant_context: ContextVar[str] = ContextVar("tenant", default=None)

# Base with placeholder schema
metadata = MetaData(schema="tenant")
Base = declarative_base(metadata=metadata)

@contextmanager
def with_tenant_db(schema: str):
    """Database session with schema translation"""
    schema_translate_map = {"tenant": schema} if schema else None
    connectable = engine.execution_options(
        schema_translate_map=schema_translate_map
    )
    db = Session(bind=connectable)
    token = tenant_context.set(schema)
    try:
        yield db
    finally:
        db.close()
        tenant_context.reset(token)

def get_db(request: Request):
    tenant = request.state.tenant  # Set by middleware
    with with_tenant_db(tenant.schema_name) as db:
        yield db
```

Middleware establishes tenant context early in the request lifecycle. This pattern uses Python's `contextvars` for async-safe, per-request isolation:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from subdomain, header, or token
        host = request.headers["host"].split(".")[0]
        
        # Lookup tenant in shared schema
        with Session(engine) as db:
            tenant = db.execute(
                select(Tenant).where(Tenant.subdomain == host)
            ).scalar_one_or_none()
            
            if not tenant:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid tenant"}
                )
        
        request.state.tenant = tenant
        token = tenant_context.set(tenant.schema_name)
        try:
            response = await call_next(request)
            return response
        finally:
            tenant_context.reset(token)

app.add_middleware(TenantMiddleware)
```

**PostgreSQL Row-Level Security** provides database-level enforcement as critical backup. Even if application code fails to filter by tenant, RLS policies prevent data leakage:

```sql
-- Enable RLS on tenant-scoped table
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

-- Create policy enforcing tenant isolation
CREATE POLICY tenant_isolation ON customers
    USING (tenant_id = current_setting('app.tenant_id')::integer);

-- Grant permissions to application role
GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user;
```

In the application, set the tenant context for the database session:

```python
def set_tenant_context(db: Session, tenant_id: int):
    db.execute(text(f"SET app.tenant_id = {tenant_id}"))

@app.middleware("http")
async def tenant_rls_middleware(request: Request, call_next):
    if hasattr(request.state, "tenant"):
        tenant_id = request.state.tenant.id
        with Session(engine) as db:
            set_tenant_context(db, tenant_id)
    response = await call_next(request)
    return response
```

**Schema design patterns** reinforce isolation. Always index `tenant_id` as the first column in composite indexes for optimal query performance. For shared-database architectures, use composite foreign keys that include `tenant_id` to enforce referential integrity within tenant boundaries:

```sql
CREATE TABLE orders (
    id SERIAL,
    tenant_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, customer_id) 
        REFERENCES customers(tenant_id, id)
        ON DELETE CASCADE,
    INDEX idx_orders_tenant (tenant_id, created_at DESC)
);
```

**File storage isolation** follows similar principles. Never trust user-provided filenames—use UUIDs or database IDs. Validate paths with strict allowlists, resolve to absolute paths, and verify they remain within tenant directories:

```python
from pathlib import Path

class TenantFileStorage:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir).resolve()
    
    def get_tenant_file_path(self, tenant_id: str, file_id: str) -> Path:
        # Validate identifiers (alphanumeric only)
        if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', tenant_id):
            raise ValueError("Invalid tenant ID")
        if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', file_id):
            raise ValueError("Invalid file ID")
        
        # Construct path
        tenant_dir = self.base_dir / tenant_id
        file_path = (tenant_dir / file_id).resolve()
        
        # Prevent path traversal
        if not str(file_path).startswith(str(tenant_dir)):
            raise ValueError("Path traversal detected")
        
        return file_path
    
    def save_file(self, tenant_id: str, file_id: str, content: bytes):
        file_path = self.get_tenant_file_path(tenant_id, file_id)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
```

For cloud storage like S3, use **prefix-based isolation** with bucket policies that enforce tenant boundaries. Each tenant's files live under `s3://bucket/tenant_id/` with IAM policies restricting access. AWS S3 Access Points provide elegant multi-tenancy with customized access policies per tenant.

Migrations in multi-tenant environments require special handling. For schema-per-tenant architectures, Alembic migrations must run across all tenant schemas:

```python
# alembic/env.py
def upgrade(schema: str):
    op.add_column(
        "customers",
        sa.Column("phone", sa.String(20)),
        schema=schema
    )

def run_migrations():
    # Get all tenant schemas
    schemas = op.get_bind().execute(
        "SELECT schema_name FROM shared.tenants"
    ).fetchall()
    
    # Run migration for each tenant
    for (schema,) in schemas:
        upgrade(schema)
```

## Dual-mode architecture enables flexible deployment options

Supporting both standalone (single-user, no authentication) and multi-tenant modes requires **strategic use of FastAPI's dependency injection system**. The key insight: determine mode at application startup or request time, then let dependencies handle the branching logic.

Configuration management with Pydantic Settings provides type-safe mode control:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    STANDALONE_MODE: bool = False
    MULTI_TENANT_ENABLED: bool = False
    AUTH_ENABLED: bool = True
    JWT_SECRET: str = ""
    
    @validator("MULTI_TENANT_ENABLED")
    def validate_exclusive_modes(cls, v, values):
        if v and values.get("STANDALONE_MODE"):
            raise ValueError("Cannot enable both modes")
        return v
    
    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Conditional dependencies** select implementations based on configuration. The factory pattern returns different dependency callables:

```python
def get_auth_dependency():
    settings = get_settings()
    if settings.STANDALONE_MODE:
        # No-op authentication for standalone
        async def no_auth():
            return {"user_id": "local", "tenant_id": "default"}
        return no_auth
    else:
        # Real JWT authentication
        return verify_jwt_token

# Create dependency at module level
auth_dep = Depends(get_auth_dependency())

@app.get("/api/items")
async def list_items(user = auth_dep, db: Session = Depends(get_db)):
    # Works in both modes
    items = db.query(Item).all()
    return items
```

**Middleware applies conditionally** at application startup:

```python
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI()
    
    # Conditional middleware
    if settings.AUTH_ENABLED and not settings.STANDALONE_MODE:
        app.add_middleware(AuthenticationMiddleware)
    
    if settings.MULTI_TENANT_ENABLED:
        app.add_middleware(TenantMiddleware)
    
    # Conditional routers
    app.include_router(common_router)
    
    if settings.STANDALONE_MODE:
        app.include_router(standalone_router)
    else:
        app.include_router(multi_tenant_router)
    
    return app

app = create_app()
```

**Abstract interfaces with strategy pattern** enable mode-specific implementations:

```python
from abc import ABC, abstractmethod

class StorageBackend(ABC):
    @abstractmethod
    async def get_data(self, key: str) -> dict:
        pass
    
    @abstractmethod
    async def save_data(self, key: str, data: dict):
        pass

class StandaloneStorage(StorageBackend):
    """Simple file-based storage for standalone mode"""
    async def get_data(self, key: str) -> dict:
        with open(f"data/{key}.json") as f:
            return json.load(f)
    
    async def save_data(self, key: str, data: dict):
        with open(f"data/{key}.json", "w") as f:
            json.dump(data, f)

class MultiTenantStorage(StorageBackend):
    """Schema-per-tenant database storage"""
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id
    
    async def get_data(self, key: str) -> dict:
        record = self.db.query(DataRecord).filter(
            DataRecord.tenant_id == self.tenant_id,
            DataRecord.key == key
        ).first()
        return record.data if record else None
    
    async def save_data(self, key: str, data: dict):
        record = DataRecord(
            tenant_id=self.tenant_id,
            key=key,
            data=data
        )
        self.db.add(record)
        self.db.commit()

def get_storage(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
) -> StorageBackend:
    if settings.STANDALONE_MODE:
        return StandaloneStorage()
    return MultiTenantStorage(db, tenant_id)
```

**Testing both modes** becomes straightforward with dependency overrides:

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def standalone_client():
    test_settings = Settings(STANDALONE_MODE=True, AUTH_ENABLED=False)
    app.dependency_overrides[get_settings] = lambda: test_settings
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()

@pytest.fixture
def multi_tenant_client():
    test_settings = Settings(
        MULTI_TENANT_ENABLED=True,
        AUTH_ENABLED=True,
        JWT_SECRET="test-secret"
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()

def test_standalone_mode(standalone_client):
    response = standalone_client.get("/api/items")
    assert response.status_code == 200

def test_multi_tenant_mode(multi_tenant_client):
    token = create_test_token(tenant_id="test-tenant")
    response = multi_tenant_client.get(
        "/api/items",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
```

Migrating from standalone to multi-tenant follows a phased approach: first, refactor to use dependency injection throughout; second, add tenant table and schema infrastructure; third, implement conditional middleware; fourth, test both modes thoroughly; finally, migrate existing data to the first tenant and switch default mode.

## Security demands multiple defensive layers and constant vigilance

Multi-tenant security failures create catastrophic breaches—one vulnerability exposes all tenant data. **The PEACH framework** from Wiz Security provides comprehensive modeling: Privilege hardening (minimize permissions), Encryption hardening (tenant-specific keys), Authentication hardening (validate certificates properly), Connectivity hardening (network controls at multiple layers), and Hygiene (clean separation of resources).

**Tenant confusion attacks** represent the highest-risk vulnerability. These occur when attackers manipulate tenant identifiers to access other tenants' data. Defense requires **always deriving tenant context from authenticated sessions**, never from client-provided values:

```python
# VULNERABLE - Client controls tenant_id
@app.post("/items")
def create_item(item: Item, tenant_id: str):  # From request body
    item.tenant_id = tenant_id  # Attacker specifies any tenant
    db.add(item)
    db.commit()

# SECURE - Tenant from authenticated token
@app.post("/items")
def create_item(
    item: Item,
    auth: dict = Depends(verify_jwt_token)
):
    tenant_id = auth["tenant_id"]  # From validated JWT
    item.tenant_id = tenant_id
    db.add(item)
    db.commit()
```

**SQL injection** remains critical despite ORMs. Always use parameterized queries, never string concatenation:

```python
# SECURE - Parameterized query
statement = select(Item).where(
    Item.tenant_id == tenant_id,
    Item.name == search_term
)
items = session.exec(statement).all()

# VULNERABLE - String concatenation (NEVER DO THIS)
query = f"SELECT * FROM items WHERE tenant_id = {tenant_id}"
# Allows: tenant_id = "1 OR 1=1"
```

**Path traversal** in file access enables attackers to read arbitrary files. Defense requires strict validation, path canonicalization, and boundary checking:

```python
def safe_file_access(tenant_id: str, filename: str) -> Path:
    # Validate filename (alphanumeric only, single extension)
    if not re.match(r'^[a-zA-Z0-9_-]+\.[a-zA-Z0-9]+$', filename):
        raise HTTPException(400, "Invalid filename")
    
    # Reject traversal sequences
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(400, "Invalid filename")
    
    # Construct and resolve path
    base_path = Path("/storage").resolve()
    tenant_path = base_path / tenant_id
    file_path = (tenant_path / filename).resolve()
    
    # Ensure path within tenant directory
    if not str(file_path).startswith(str(tenant_path)):
        raise HTTPException(403, "Access denied")
    
    return file_path
```

**Rate limiting** prevents abuse and resource exhaustion. Implement per-tenant limits using Redis for distributed rate limiting:

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

@app.on_event("startup")
async def startup():
    redis_client = await redis.from_url("redis://localhost")
    await FastAPILimiter.init(redis_client)

# Per-tenant rate limiting
def get_tenant_rate_limit(tenant: Tenant = Depends(get_tenant)):
    # Different limits by tier
    limits = {
        "free": (100, 3600),      # 100 requests per hour
        "premium": (1000, 3600),   # 1000 requests per hour
        "enterprise": (10000, 3600) # 10000 requests per hour
    }
    times, seconds = limits.get(tenant.tier, (100, 3600))
    return RateLimiter(times=times, seconds=seconds)

@app.get("/api/resource")
async def resource(
    rate_limit: RateLimiter = Depends(get_tenant_rate_limit),
    tenant: Tenant = Depends(get_tenant)
):
    return {"message": "Success"}
```

**Comprehensive audit logging** enables security monitoring and incident response:

```python
import logging
import json
from datetime import datetime

class SecurityAuditLogger:
    def __init__(self):
        self.logger = logging.getLogger("security_audit")
        handler = logging.handlers.RotatingFileHandler(
            "security_audit.log",
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        self.logger.addHandler(handler)
    
    def log_access(
        self,
        tenant_id: str,
        user_id: str,
        resource: str,
        action: str,
        result: str,
        ip_address: str
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "result": result,
            "ip_address": ip_address
        }
        self.logger.info(json.dumps(log_entry))

audit = SecurityAuditLogger()

@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    response = await call_next(request)
    
    audit.log_access(
        tenant_id=tenant_id,
        user_id=user_id,
        resource=request.url.path,
        action=request.method,
        result=str(response.status_code),
        ip_address=request.client.host
    )
    
    return response
```

Log all security-relevant events: authentication attempts, authorization decisions, tenant context switches, cross-tenant access attempts, privilege escalations, rate limit violations, and configuration changes.

**Security headers** protect against common web vulnerabilities:

```python
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

Production deployment checklist: All secrets in environment variables; HTTPS enabled with valid certificates; rate limiting configured; comprehensive logging enabled; monitoring and alerting configured; database uses least-privilege accounts; Row-Level Security enabled; CORS configured restrictively; security headers implemented; input validation on all endpoints; tenant isolation tested with penetration testing; error messages sanitized to not leak sensitive info; dependencies scanned for vulnerabilities; incident response procedures documented.

## Practical implementation patterns and architectural tradeoffs

Real-world production systems combine these patterns based on specific requirements. The **recommended stack for most SaaS applications**: PostgreSQL schema-per-tenant architecture, subdomain-based tenant identification for web interfaces with JWT claims for APIs, FastAPI Users for authentication, SQLAlchemy with schema translation for database access, Redis for session storage and rate limiting, Row-Level Security as defense-in-depth, and comprehensive audit logging with Prometheus metrics.

**Schema migrations** in multi-tenant environments require orchestration across tenants. Create a migration runner that tracks which tenants have received which migrations:

```python
# Migration tracking table in shared schema
class MigrationStatus(Base):
    __tablename__ = "migration_status"
    __table_args__ = {"schema": "shared"}
    
    tenant_id = Column(Integer, primary_key=True)
    migration_version = Column(String, primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # 'success', 'failed', 'in_progress'

def run_tenant_migration(tenant_schema: str, migration_func):
    try:
        # Run migration for this tenant
        migration_func(schema=tenant_schema)
        
        # Record success
        record_migration_status(tenant_schema, "success")
    except Exception as e:
        record_migration_status(tenant_schema, "failed", error=str(e))
        raise

def migrate_all_tenants():
    tenants = get_all_tenant_schemas()
    
    for tenant_schema in tenants:
        if needs_migration(tenant_schema, current_migration):
            run_tenant_migration(tenant_schema, upgrade_schema)
```

**Performance optimization** focuses on connection pooling and caching. Use SQLAlchemy's connection pool efficiently—don't create new engines per request. Cache tenant metadata in Redis with reasonable TTL:

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

def get_tenant_cached(subdomain: str) -> dict:
    cache_key = f"tenant:{subdomain}"
    
    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Query database
    with Session(engine) as db:
        tenant = db.query(Tenant).filter(
            Tenant.subdomain == subdomain
        ).first()
        
        if tenant:
            tenant_data = {
                "id": tenant.id,
                "schema_name": tenant.schema_name,
                "tier": tenant.tier
            }
            # Cache for 5 minutes
            redis_client.setex(cache_key, 300, json.dumps(tenant_data))
            return tenant_data
    
    return None
```

**Error handling** must not leak sensitive information while providing useful debugging:

```python
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log detailed error internally
    logger.error(
        f"Unhandled exception: {exc}",
        extra={
            "tenant_id": getattr(request.state, "tenant_id", None),
            "user_id": getattr(request.state, "user_id", None),
            "path": request.url.path,
            "traceback": traceback.format_exc()
        }
    )
    
    # Return generic error to client
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

**Monitoring with Prometheus** tracks multi-tenant health:

```python
from prometheus_client import Counter, Histogram

request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'tenant_id', 'status_code']
)

tenant_isolation_violations = Counter(
    'tenant_isolation_violations_total',
    'Attempted tenant isolation violations',
    ['tenant_id', 'target_tenant_id']
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    tenant_id = getattr(request.state, "tenant_id", "unknown")
    
    response = await call_next(request)
    
    request_count.labels(
        method=request.method,
        endpoint=request.url.path,
        tenant_id=tenant_id,
        status_code=response.status_code
    ).inc()
    
    return response
```

## Conclusion: Multi-tenancy is an architectural commitment requiring orchestration

Building production-ready multi-tenant FastAPI applications requires no single library but rather orchestrating FastAPI's native capabilities with strategic architectural decisions. Success hinges on three principles: establish tenant context early and enforce at every layer, treat multi-tenancy as an authorization concern requiring constant validation, and implement defense-in-depth with application, database, and infrastructure security.

The schema-per-tenant pattern with PostgreSQL provides the optimal balance for most SaaS applications, scaling to thousands of tenants while maintaining strong isolation. FastAPI Users delivers comprehensive authentication, while security demands Row-Level Security, parameterized queries, strict input validation, comprehensive audit logging, and rate limiting. Supporting both standalone and multi-tenant modes becomes manageable through dependency injection and conditional configuration.

Start with clear architectural decisions based on tenant count, compliance requirements, and budget. Implement tenant isolation from day one—retrofitting is exponentially harder. Test tenant isolation exhaustively, including penetration testing specifically targeting cross-tenant access. Monitor continuously with tenant-scoped metrics and comprehensive audit logs. As your application scales, the architectural patterns described here provide a foundation for secure, maintainable multi-tenant SaaS applications.