"""Database configuration and FastAPI Users setup."""

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base, User

# mypy cannot see that the SQLAlchemy ``Mapped[...]`` columns on ``User``
# satisfy fastapi-users' ``UserProtocol`` when checking type-variable bounds
# (it compares the class-level descriptor types, not the instance attribute
# types); the model does satisfy the protocol at runtime.
UserDatabase = SQLAlchemyUserDatabase[User, uuid.UUID]  # type: ignore[type-var]


# Database URL - using SQLite by default, stored in user's home directory
def get_database_url() -> str:
    """Get database URL from environment variable or default location.

    Priority:
    1. WRITING_ASSISTANT_DB_PATH environment variable
    2. Default: ~/.writing_assistant/writing_assistant.db
    """
    db_path_env = os.getenv("WRITING_ASSISTANT_DB_PATH")

    if db_path_env:
        # Use provided path
        db_path = Path(db_path_env).expanduser().resolve()
        # Create parent directory if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Default location
        home_dir = Path.home()
        db_dir = home_dir / ".writing_assistant"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "writing_assistant.db"

    return f"sqlite+aiosqlite:///{db_path}"


# Lazy initialization - these will be created when first accessed
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        _engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL query logging
            connect_args=(
                {"check_same_thread": False} if "sqlite" in database_url else {}
            ),
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def create_db_and_tables() -> None:
    """Create database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[UserDatabase, None]:
    """Dependency to get user database."""
    yield UserDatabase(session, User)  # type: ignore[type-var]  # see UserDatabase
