from __future__ import annotations

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
async def admin_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "admin@example.com", "password": "Pass123!"})
        yield client


@pytest.fixture
async def member_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "member@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "member@example.com", "password": "Pass123!"})
        yield client


@pytest.mark.asyncio
async def test_non_admin_cannot_list_audit_events(member_client):
    response = await member_client.get("/v1/audit/events")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_admin_can_list_and_filter_audit_events(admin_client):
    create_response = await admin_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "audit-box"},
        headers={"X-Request-Id": "req-admin-audit"},
    )
    sandbox_id = create_response.json()["id"]

    response = await admin_client.get(
        "/v1/audit/events",
        params={
            "action": "sandbox.create",
            "target_type": "sandbox",
            "target_id": sandbox_id,
            "request_id": "req-admin-audit",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["action"] == "sandbox.create"
    assert data["items"][0]["target_id"] == sandbox_id
    assert data["items"][0]["request_id"] == "req-admin-audit"
