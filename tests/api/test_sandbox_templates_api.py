"""API tests for Sandbox Templates endpoint."""

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User


@pytest.fixture
async def db_session():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    async def override_get_user_db():
        async with factory() as session:
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

    async def override_get_user_manager():
        async with factory() as session:
            db = SQLAlchemyUserDatabase(session, User, OAuthAccount)
            yield UserManager(db)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_user_db] = override_get_user_db
    app.dependency_overrides[get_user_manager] = override_get_user_manager
    yield
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def auth_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "tmpl@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "tmpl@test.com", "password": "Pass123!"})
        yield client


async def test_list_templates_requires_auth(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/sandbox-templates")
    assert resp.status_code == 401


async def test_list_templates_returns_items(auth_client):
    resp = await auth_client.get("/v1/sandbox-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 5
    names = [t["name"] for t in data["items"]]
    assert "aio-sandbox-tiny" in names


async def test_template_has_expected_fields(auth_client):
    resp = await auth_client.get("/v1/sandbox-templates")
    tmpl = resp.json()["items"][0]
    assert "name" in tmpl
    assert "display_name" in tmpl
    assert "image" in tmpl
    assert "resource_spec" in tmpl
    assert "runtime_type" not in tmpl
