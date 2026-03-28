"""Tests for the Usage API (GET /v1/usage/*).

Covers F24: Usage API endpoints accessible by authenticated users.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.metering import TierTemplate
from treadstone.models.user import OAuthAccount, User

_test_session_factory: async_sessionmaker | None = None


async def _seed_tier_templates(session: AsyncSession) -> None:
    """Insert default TierTemplate rows required by MeteringService."""
    defaults = [
        TierTemplate(
            tier_name="free",
            compute_credits_monthly=Decimal("10"),
            storage_capacity_gib=0,
            max_concurrent_running=1,
            max_sandbox_duration_seconds=1800,
            allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small"],
            grace_period_seconds=600,
        ),
        TierTemplate(
            tier_name="pro",
            compute_credits_monthly=Decimal("100"),
            storage_capacity_gib=10,
            max_concurrent_running=3,
            max_sandbox_duration_seconds=7200,
            allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"],
            grace_period_seconds=1800,
        ),
    ]
    for t in defaults:
        session.add(t)
    await session.commit()


@pytest.fixture
async def db_session():
    global _test_session_factory
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with _test_session_factory() as session:
        await _seed_tier_templates(session)

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
async def user_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "user@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "user@example.com", "password": "Pass123!"})
        yield client


# ── GET /v1/usage ────────────────────────────────────────────────────────────


async def test_get_usage_returns_summary(user_client):
    resp = await user_client.get("/v1/usage")
    assert resp.status_code == 200
    data = resp.json()

    assert data["tier"] == "free"
    assert "billing_period" in data
    assert data["billing_period"]["start"] is not None
    assert data["billing_period"]["end"] is not None

    assert data["compute"]["vcpu_hours"] == 0.0
    assert data["compute"]["memory_gib_hours"] == 0.0

    assert data["storage"]["gib_hours"] == 0.0
    assert data["storage"]["current_used_gib"] == 0
    assert data["storage"]["total_quota_gib"] == 0
    assert data["storage"]["available_gib"] == 0

    assert data["limits"]["max_concurrent_running"] == 1
    assert data["limits"]["allowed_templates"] == ["aio-sandbox-tiny", "aio-sandbox-small"]

    assert data["grace_period"]["active"] is False
    assert data["grace_period"]["grace_period_seconds"] == 600


async def test_get_usage_includes_extra_credits(user_client):
    """Welcome compute grant is listed under /v1/usage/grants; summary compute is raw usage only."""
    usage = await user_client.get("/v1/usage")
    assert usage.status_code == 200
    u = usage.json()
    assert u["compute"]["vcpu_hours"] == 0.0
    assert u["compute"]["memory_gib_hours"] == 0.0

    grants = await user_client.get("/v1/usage/grants")
    assert grants.status_code == 200
    welcome = next((g for g in grants.json()["items"] if g["grant_type"] == "welcome_bonus"), None)
    assert welcome is not None
    assert welcome["credit_type"] == "compute"
    assert welcome["remaining_amount"] == 50.0

    plan = await user_client.get("/v1/usage/plan")
    assert plan.status_code == 200
    assert plan.json()["compute_credits_monthly_limit"] == 10.0
    assert plan.json()["compute_credits_monthly_used"] == 0.0


async def test_get_usage_unauthenticated(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/usage")
        assert resp.status_code == 401


# ── GET /v1/usage/plan ───────────────────────────────────────────────────────


async def test_get_plan_returns_full_details(user_client):
    resp = await user_client.get("/v1/usage/plan")
    assert resp.status_code == 200
    data = resp.json()

    assert data["tier"] == "free"
    assert data["compute_credits_monthly_limit"] == 10.0
    assert data["compute_credits_monthly_used"] == 0.0
    assert data["storage_capacity_limit_gib"] == 0
    assert data["max_concurrent_running"] == 1
    assert data["max_sandbox_duration_seconds"] == 1800
    assert data["allowed_templates"] == ["aio-sandbox-tiny", "aio-sandbox-small"]
    assert data["grace_period_seconds"] == 600
    assert data["billing_period_start"] is not None
    assert data["billing_period_end"] is not None
    assert data["grace_period_started_at"] is None


# ── GET /v1/usage/sessions ───────────────────────────────────────────────────


async def test_list_sessions_empty(user_client):
    resp = await user_client.get("/v1/usage/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


async def test_list_sessions_with_status_filter(user_client):
    resp = await user_client.get("/v1/usage/sessions", params={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await user_client.get("/v1/usage/sessions", params={"status": "completed"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_sessions_invalid_status_rejected(user_client):
    resp = await user_client.get("/v1/usage/sessions", params={"status": "invalid"})
    assert resp.status_code == 422


async def test_list_sessions_pagination(user_client):
    resp = await user_client.get("/v1/usage/sessions", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


# ── GET /v1/usage/grants ────────────────────────────────────────────────────


async def test_list_grants_includes_welcome_bonus(user_client):
    resp = await user_client.get("/v1/usage/grants")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 1

    welcome = next((g for g in data["items"] if g["grant_type"] == "welcome_bonus"), None)
    assert welcome is not None
    assert welcome["credit_type"] == "compute"
    assert welcome["original_amount"] == 50.0
    assert welcome["remaining_amount"] == 50.0
    assert welcome["status"] == "active"


async def test_list_grants_shows_correct_status(user_client):
    resp = await user_client.get("/v1/usage/grants")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] in ("active", "exhausted", "expired")
