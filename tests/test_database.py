"""Tests for database.py configuration and functions."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_get_database_url_default():
    """Test get_database_url with default location."""
    from writing_assistant.app.database import get_database_url

    with patch.dict(os.environ, {}, clear=True):
        url = get_database_url()
        assert "sqlite+aiosqlite:///" in url
        assert ".writing_assistant" in url
        assert "writing_assistant.db" in url


def test_get_database_url_custom_path():
    """Test get_database_url with custom WRITING_ASSISTANT_DB_PATH."""
    from writing_assistant.app.database import get_database_url

    custom_path = "/tmp/test_custom.db"
    with patch.dict(os.environ, {"WRITING_ASSISTANT_DB_PATH": custom_path}):
        url = get_database_url()
        assert "sqlite+aiosqlite:///" in url
        assert "test_custom.db" in url


def test_get_database_url_creates_parent_directory():
    """Test that get_database_url creates parent directory if needed."""
    import tempfile

    from writing_assistant.app.database import get_database_url

    with tempfile.TemporaryDirectory() as tmpdir:
        custom_path = f"{tmpdir}/subdir/test.db"
        with patch.dict(os.environ, {"WRITING_ASSISTANT_DB_PATH": custom_path}):
            url = get_database_url()
            parent_dir = Path(custom_path).parent
            assert parent_dir.exists()


def test_get_engine():
    """Test get_engine creates and caches engine."""
    from writing_assistant.app import database

    # Reset the global engine
    database._engine = None

    engine1 = database.get_engine()
    assert engine1 is not None

    # Should return the same instance
    engine2 = database.get_engine()
    assert engine1 is engine2


def test_get_session_maker():
    """Test get_session_maker creates and caches session maker."""
    from writing_assistant.app import database

    # Reset the global session maker
    database._async_session_maker = None

    maker1 = database.get_session_maker()
    assert maker1 is not None

    # Should return the same instance
    maker2 = database.get_session_maker()
    assert maker1 is maker2


@pytest.mark.asyncio
async def test_create_db_and_tables():
    """Test create_db_and_tables function."""
    from writing_assistant.app import database
    from writing_assistant.app.database import create_db_and_tables

    # Reset globals to force new engine creation
    database._engine = None
    database._async_session_maker = None

    # Should not raise any errors
    await create_db_and_tables()


@pytest.mark.asyncio
async def test_get_async_session():
    """Test get_async_session generator."""
    from writing_assistant.app import database
    from writing_assistant.app.database import get_async_session

    # Reset globals
    database._engine = None
    database._async_session_maker = None

    # Test the async generator
    async for session in get_async_session():
        assert session is not None
        # Should only yield once
        break


@pytest.mark.asyncio
async def test_get_user_db(async_db_session):
    """Test get_user_db dependency."""
    from writing_assistant.app.database import get_user_db

    # Test the async generator
    async for user_db in get_user_db(async_db_session):
        assert user_db is not None
        # Should only yield once
        break
