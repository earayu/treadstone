"""API tests for API Key CRUD endpoints."""

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User

_test_session_factory = None


@pytest.fixture
async def db_session():
    global _test_session_factory
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with _test_session_factory() as session:
            yield session

    async def override_get_user_db():
        async with _test_session_factory() as session:
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

    async def override_get_user_manager():
        async with _test_session_factory() as session:
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
    """Register + login, return client with auth cookie."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "keyuser@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "keyuser@test.com", "password": "Pass123!"})
        yield client


async def test_create_api_key(auth_client):
    resp = await auth_client.post("/v1/auth/api-keys", json={"name": "test-key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["key"].startswith("sk-")
    assert "id" in data


async def test_list_api_keys(auth_client):
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-1"})
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-2"})
    resp = await auth_client.get("/v1/auth/api-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2
    for item in data["items"]:
        assert "key" not in item
        assert "key_prefix" in item


async def test_delete_api_key(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "to-delete"})
    key_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/v1/auth/api-keys/{key_id}")
    assert resp.status_code == 204
