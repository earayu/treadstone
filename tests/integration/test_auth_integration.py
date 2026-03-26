"""Integration tests for the auth system against real Neon DB.

These tests create real users in the database and clean up after themselves.
Uses Neon test branch if tests/integration/.env.test exists; otherwise falls back
to the default TREADSTONE_DATABASE_URL.

Run with: make test-all
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import treadstone.core.database as db_mod
from treadstone.main import app
from treadstone.models.api_key import ApiKey
from treadstone.models.user import OAuthAccount, User

from .conftest import _load_test_db_url

UNIQUE = secrets.token_hex(4)
TEST_EMAIL = f"inttest-{UNIQUE}@test.treadstone.dev"
TEST_EMAIL_2 = f"inttest2-{UNIQUE}@test.treadstone.dev"
TEST_PASSWORD = "IntTest_Str0ng!"


def _make_engine():
    """Create a fresh async engine for cleanup (avoids event loop conflicts)."""
    return db_mod._build_engine(url=_load_test_db_url())


@pytest.fixture(autouse=True)
async def cleanup_test_users():
    """Clean up any test users created during tests."""
    yield
    eng = _make_engine()
    session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        user_ids_result = await session.execute(select(User.id).where(User.email.like(f"inttest%{UNIQUE}%")))
        user_ids = [row[0] for row in user_ids_result.fetchall()]
        if user_ids:
            await session.execute(delete(ApiKey).where(ApiKey.user_id.in_(user_ids)))
            await session.execute(delete(OAuthAccount).where(OAuthAccount.user_id.in_(user_ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()
    await eng.dispose()


@pytest.mark.integration
async def test_tables_exist():
    """Verify all auth tables were created by Alembic migration."""
    eng = _make_engine()
    session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        for table in ("user", "oauth_account", "api_key"):
            result = await session.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"),
                {"t": table},
            )
            assert result.scalar() is True, f"Table '{table}' does not exist"
        invitation_result = await session.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'invitation')")
        )
        assert invitation_result.scalar() is False
    await eng.dispose()


@pytest.mark.integration
async def test_register_creates_user_in_db():
    """Register via API and verify user exists in real DB."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == TEST_EMAIL

    eng = _make_engine()
    session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            text('SELECT id, email, role FROM "user" WHERE email = :e'),
            {"e": TEST_EMAIL},
        )
        row = result.fetchone()
        assert row is not None
        assert row.email == TEST_EMAIL
    await eng.dispose()


@pytest.mark.integration
async def test_full_auth_flow():
    """End-to-end: register -> login -> get user -> change password -> login with new password."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg_resp = await client.post(
            "/v1/auth/register",
            json={"email": TEST_EMAIL_2, "password": TEST_PASSWORD},
        )
        assert reg_resp.status_code == 201

        login_resp = await client.post(
            "/v1/auth/login",
            json={"email": TEST_EMAIL_2, "password": TEST_PASSWORD},
        )
        assert login_resp.status_code == 200
        session_cookie = login_resp.cookies.get("session")
        assert session_cookie is not None

        client.cookies.set("session", session_cookie)
        user_resp = await client.get("/v1/auth/user")
        assert user_resp.status_code == 200
        assert user_resp.json()["email"] == TEST_EMAIL_2

        new_password = "NewStr0ng_Pass!"
        change_resp = await client.post(
            "/v1/auth/change-password",
            json={"old_password": TEST_PASSWORD, "new_password": new_password},
        )
        assert change_resp.status_code == 200

        logout_resp = await client.post("/v1/auth/logout")
        assert logout_resp.status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login2_resp = await client.post(
            "/v1/auth/login",
            json={"email": TEST_EMAIL_2, "password": new_password},
        )
        assert login2_resp.status_code == 200
        assert login2_resp.cookies.get("session") is not None


@pytest.mark.integration
async def test_duplicate_register_returns_409():
    """Registering same email twice returns 409 Conflict."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        resp = await client.post("/v1/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 409


@pytest.mark.integration
async def test_config_endpoint_returns_auth_info():
    """/v1/config returns auth configuration from real app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth"]["type"] == "cookie"
    assert "email" in data["auth"]["login_methods"]
