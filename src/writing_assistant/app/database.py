"""Database configuration and FastAPI Users setup."""

import os
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, User


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
_engine = None
_async_session_maker = None

def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        _engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL query logging
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        )
    return _engine

def get_session_maker():
    """Get or create the async session maker."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def create_db_and_tables():
    """Create database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """Dependency to get user database."""
    yield SQLAlchemyUserDatabase(session, User)
