"""Database configuration and FastAPI Users setup."""

from typing import AsyncGenerator
import uuid
from pathlib import Path

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base, User


# Database URL - using SQLite by default, stored in user's home directory
def get_database_url() -> str:
    """Get database URL, defaulting to SQLite in user's home directory."""
    home_dir = Path.home()
    db_dir = home_dir / ".writing_assistant"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "writing_assistant.db"
    return f"sqlite+aiosqlite:///{db_path}"


DATABASE_URL = get_database_url()

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables():
    """Create database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    """Dependency to get user database."""
    yield SQLAlchemyUserDatabase(session, User)
