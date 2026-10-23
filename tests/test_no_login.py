"""Tests for no-login mode (``writing-assistant --no-login``)."""

import json

import pytest
from fastapi.testclient import TestClient
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from writing_assistant.app import main as main_module
from writing_assistant.app.models import User


@pytest.fixture
def no_login(monkeypatch):
    """Switch the app into no-login mode the way ``server.main`` does."""
    main_module.enable_no_login()
    yield
    main_module.NO_LOGIN = False
    main_module.app.dependency_overrides.pop(main_module.current_active_user, None)


def test_requests_need_no_token(no_login, client: TestClient):
    response = client.get("/auth/check")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == main_module.NO_LOGIN_EMAIL
    assert data["no_login"] is True


def test_documents_work_without_a_token(no_login, client: TestClient):
    document = {"title": "Local", "sections": []}
    saved = client.post(
        "/documents/save",
        data={"filename": "local.json", "document_data": json.dumps(document)},
    )
    assert saved.status_code == 200

    listed = client.get("/documents/list").json()["files"]
    assert [f["filename"] for f in listed] == ["local.json"]
    loaded = client.get("/documents/load/local.json").json()
    assert loaded["document"] == document


async def test_single_user_without_a_usable_password(
    no_login, client: TestClient, async_db_session: AsyncSession
):
    for _ in range(3):
        assert client.get("/auth/check").status_code == 200

    users = (await async_db_session.execute(select(User))).scalars().all()
    assert [u.email for u in users] == [main_module.NO_LOGIN_EMAIL]
    # "No password" means nobody types one, not that an empty one works:
    # the same database opened without --no-login must not let anyone in.
    verified, _ = PasswordHelper().verify_and_update("", users[0].hashed_password)
    assert not verified
    login = client.post(
        "/auth/jwt/login",
        data={"username": main_module.NO_LOGIN_EMAIL, "password": ""},
    )
    assert login.status_code != 200


async def test_startup_creates_the_user_once(no_login, async_db_session):
    from writing_assistant.app.models import Base

    async with async_db_session.bind.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    first = await main_module.ensure_no_login_user(async_db_session)
    second = await main_module.ensure_no_login_user(async_db_session)

    assert first.id == second.id
    count = await async_db_session.scalar(select(func.count()).select_from(User))
    assert count == 1


@pytest.mark.parametrize("page", ["/login", "/register"])
def test_login_pages_go_straight_to_the_editor(no_login, client, page):
    response = client.get(page, follow_redirects=False)

    assert response.status_code in (302, 303, 307)
    assert response.headers["location"] == "/"


def test_config_and_health_report_the_mode(no_login, client):
    assert client.get("/config").json()["no_login"] is True
    assert client.get("/health").json()["no_login"] is True


def test_normal_mode_is_unchanged(client):
    assert client.get("/auth/check").status_code == 401
    assert client.get("/login").status_code == 200
    assert client.get("/config").json()["no_login"] is False
    assert client.get("/health").json()["no_login"] is False
