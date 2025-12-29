"""Pytest configuration and fixtures."""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from writing_assistant.app.auth import get_user_manager
from writing_assistant.app.database import get_async_session, get_user_db
from writing_assistant.app.main import app
from writing_assistant.app.models import Base, User

# Create a test database engine (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


def pytest_sessionfinish(session, exitstatus):
    """Clean up async engine after all tests complete."""
    import asyncio

    # Dispose of the async engine to close all connections and threads
    try:
        # Try to dispose using the current event loop if available
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed() and not loop.is_running():
                loop.run_until_complete(test_engine.dispose())
            else:
                # Create a new event loop for cleanup
                asyncio.run(test_engine.dispose())
        except RuntimeError:
            # No event loop exists, create one
            asyncio.run(test_engine.dispose())
    except Exception:
        # Fallback: try to close the underlying sync engine
        try:
            test_engine.sync_engine.dispose(close=True)
        except Exception:
            pass


@pytest.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database for each test."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        yield session

    # Drop tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def client(async_db_session: AsyncSession):
    """Create a test client with overridden database dependency."""

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(async_db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    from fastapi_users.password import PasswordHelper

    password_helper = PasswordHelper()
    hashed_password = password_helper.hash("testpassword123")

    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )

    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)

    return user


@pytest.fixture
def authenticated_client(client: TestClient, async_db_session: AsyncSession, test_user: User) -> TestClient:
    """Create an authenticated test client with a valid JWT token."""
    # Login to get JWT token
    login_response = client.post(
        "/auth/jwt/login",
        data={"username": "test@example.com", "password": "testpassword123"},
    )

    assert login_response.status_code == 200
    token_data = login_response.json()
    token = token_data["access_token"]

    # Set default authorization header
    client.headers["Authorization"] = f"Bearer {token}"

    return client


@pytest.fixture
def sample_metadata():
    """Sample metadata for testing."""
    from writing_assistant.core.definitions import Metadata

    metadata = Metadata()
    metadata.writing_style = "formal"
    metadata.target_audience = "academic"
    metadata.tone = "professional"
    metadata.background_context = "test context"
    metadata.generation_directive = "be clear and concise"
    metadata.word_limit = 100
    return metadata