from datetime import timedelta

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.api import auth as auth_api
from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import Invitation, OAuthAccount, User, utc_now

_test_session_factory = None


@pytest.fixture
async def db_session():
    """In-memory SQLite for isolated API tests."""
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


@pytest.mark.asyncio
async def test_register_first_user_becomes_admin(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/register",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_register_duplicate_email(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "a@b.com", "password": "Pass123!"})
        resp = await client.post("/v1/auth/register", json={"email": "a@b.com", "password": "Pass123!"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "u@b.com", "password": "Pass123!"})
        resp = await client.post("/v1/auth/login", json={"email": "u@b.com", "password": "Pass123!"})
    assert resp.status_code == 200
    assert "session" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "x@b.com", "password": "Pass123!"})
        resp = await client.post("/v1/auth/login", json={"email": "x@b.com", "password": "WRONG"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email_returns_422(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/register", json={"email": "not-an-email", "password": "Pass123!"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_get_user_after_login(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "me@b.com", "password": "Pass123!"})
        login_resp = await client.post("/v1/auth/login", json={"email": "me@b.com", "password": "Pass123!"})
        cookies = login_resp.cookies
        resp = await client.get("/v1/auth/user", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@b.com"


@pytest.mark.asyncio
async def test_register_with_invalid_invitation_role_does_not_500(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "register_mode", "invitation")

    async with _test_session_factory() as session:
        admin = User(
            email="admin@test.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            role="admin",
        )
        invitation = Invitation(
            email="invitee@test.com",
            token="bad-role-token",
            created_by="admin@test.com",
            expires_at=utc_now() + timedelta(days=1),
            role="not-a-role",
        )
        session.add(admin)
        session.add(invitation)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/register",
            json={
                "email": "invitee@test.com",
                "password": "Pass123!",
                "invitation_token": "bad-role-token",
            },
        )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
