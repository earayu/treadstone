"""Tests for the Usage API (GET /v1/usage/*).

Covers F24: Usage API endpoints accessible by authenticated users.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.metering import (
    ComputeGrant,
    ComputeSession,
    StorageLedger,
    StorageQuotaGrant,
    StorageState,
    TierTemplate,
    UserPlan,
)
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import OAuthAccount, User

_test_session_factory: async_sessionmaker | None = None


async def _seed_tier_templates(session: AsyncSession) -> None:
    """Insert default TierTemplate rows required by MeteringService."""
    defaults = [
        TierTemplate(
            tier_name="free",
            compute_units_monthly=Decimal("10"),
            storage_capacity_gib=0,
            max_concurrent_running=1,
            max_sandbox_duration_seconds=1800,
            allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small"],
            grace_period_seconds=600,
        ),
        TierTemplate(
            tier_name="pro",
            compute_units_monthly=Decimal("100"),
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

    assert data["compute"]["compute_unit_hours"] == 0.0
    assert data["compute"]["monthly_limit"] == 10.0
    assert data["compute"]["monthly_used"] == 0.0
    assert data["compute"]["monthly_remaining"] == 10.0
    assert data["compute"]["extra_remaining"] == 0.0
    assert data["compute"]["total_remaining"] == 10.0
    assert data["compute"]["unit"] == "CU-hours"

    assert data["storage"]["gib_hours"] == 0.0
    assert data["storage"]["current_used_gib"] == 0
    assert data["storage"]["total_quota_gib"] == 0
    assert data["storage"]["available_gib"] == 0
    assert data["storage"]["unit"] == "GiB"

    assert data["limits"]["max_concurrent_running"] == 1
    assert data["limits"]["allowed_templates"] == ["aio-sandbox-tiny", "aio-sandbox-small"]

    assert data["grace_period"]["active"] is False
    assert data["grace_period"]["grace_period_seconds"] == 600


async def test_get_usage_includes_credit_pool_and_grants(user_client):
    """Usage summary includes credit pool status; no welcome bonus when amount is 0."""
    usage = await user_client.get("/v1/usage")
    assert usage.status_code == 200
    u = usage.json()
    assert u["compute"]["compute_unit_hours"] == 0.0
    assert u["compute"]["monthly_limit"] == 10.0
    assert u["compute"]["monthly_used"] == 0.0
    assert u["compute"]["extra_remaining"] == 0.0
    assert u["compute"]["total_remaining"] == 10.0

    grants = await user_client.get("/v1/usage/grants")
    assert grants.status_code == 200
    compute = grants.json()["compute_grants"]
    welcome = next((g for g in compute if g["grant_type"] == "welcome_bonus"), None)
    assert welcome is None

    plan = await user_client.get("/v1/usage/plan")
    assert plan.status_code == 200
    assert plan.json()["compute_units_monthly_limit"] == 10.0
    assert plan.json()["compute_units_monthly_used"] == 0.0


async def test_get_usage_clips_cross_period_cumulative_usage(user_client, monkeypatch):
    fixed_now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: fixed_now)

    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "user@example.com"))).unique().scalar_one()

        sandbox = Sandbox(
            id="sbperiodoverlap001",
            name="period-overlap",
            owner_id=user.id,
            template="aio-sandbox-small",
            k8s_namespace="test",
            status=SandboxStatus.STOPPED,
            endpoints={},
        )
        session.add(sandbox)

        session.add(
            ComputeSession(
                id="csperiodoverlap001",
                sandbox_id=sandbox.id,
                user_id=user.id,
                template="aio-sandbox-small",
                vcpu_request=Decimal("1"),
                memory_gib_request=Decimal("2"),
                started_at=datetime(2026, 2, 28, 23, 0, 0, tzinfo=UTC),
                ended_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
                last_metered_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
                vcpu_hours=Decimal("2"),
                memory_gib_hours=Decimal("4"),
            )
        )
        session.add(
            StorageLedger(
                id="slperiodoverlap001",
                user_id=user.id,
                sandbox_id=sandbox.id,
                size_gib=5,
                storage_state=StorageState.DELETED,
                allocated_at=datetime(2026, 2, 28, 23, 0, 0, tzinfo=UTC),
                released_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
                gib_hours_consumed=Decimal("10"),
                last_metered_at=datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    resp = await user_client.get("/v1/usage")

    assert resp.status_code == 200
    data = resp.json()
    # Sum formula: 0.5*vcpu_hours + 0.125*memory_gib_hours; overlap_ratio 0.5 → 1.5 * 0.5 = 0.75
    assert data["compute"]["compute_unit_hours"] == 0.75
    assert data["storage"]["gib_hours"] == 5.0


async def test_get_usage_surfaces_negative_total_remaining_when_user_has_overage(user_client):
    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "user@example.com"))).unique().scalar_one()
        user_plan = (await session.execute(select(UserPlan).where(UserPlan.user_id == user.id))).scalar_one()
        user_plan.compute_units_monthly_used = Decimal("10")
        user_plan.compute_units_overage = Decimal("2.5")
        user_plan.grace_period_started_at = datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC)
        session.add(user_plan)
        await session.commit()

    resp = await user_client.get("/v1/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["compute"]["monthly_remaining"] == 0.0
    assert data["compute"]["extra_remaining"] == 0.0
    assert data["compute"]["total_remaining"] == -2.5


async def test_grants_exactly_at_expiry_align_with_usage_summary(user_client, monkeypatch):
    fixed_now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: fixed_now)
    monkeypatch.setattr("treadstone.api.metering_serializers.utc_now", lambda: fixed_now)

    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "user@example.com"))).unique().scalar_one()
        session.add(
            ComputeGrant(
                id="cgexactexpiry000001",
                user_id=user.id,
                grant_type="promo",
                original_amount=Decimal("5"),
                remaining_amount=Decimal("5"),
                granted_at=fixed_now,
                expires_at=fixed_now,
            )
        )
        session.add(
            StorageQuotaGrant(
                id="sqgexactexpiry00001",
                user_id=user.id,
                grant_type="promo",
                size_gib=7,
                granted_at=fixed_now,
                expires_at=fixed_now,
            )
        )
        await session.commit()

    usage_resp = await user_client.get("/v1/usage")
    grants_resp = await user_client.get("/v1/usage/grants")

    assert usage_resp.status_code == 200
    assert usage_resp.json()["compute"]["extra_remaining"] == 0.0
    assert usage_resp.json()["storage"]["total_quota_gib"] == 0

    assert grants_resp.status_code == 200
    body = grants_resp.json()
    compute = next(item for item in body["compute_grants"] if item["id"] == "cgexactexpiry000001")
    storage = next(item for item in body["storage_quota_grants"] if item["id"] == "sqgexactexpiry00001")
    assert compute["status"] == "expired"
    assert storage["status"] == "expired"


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
    assert data["compute_units_monthly_limit"] == 10.0
    assert data["compute_units_monthly_used"] == 0.0
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


async def test_list_grants_no_welcome_bonus_when_disabled(user_client):
    resp = await user_client.get("/v1/usage/grants")
    assert resp.status_code == 200
    data = resp.json()
    assert "compute_grants" in data
    assert "storage_quota_grants" in data

    welcome = next((g for g in data["compute_grants"] if g["grant_type"] == "welcome_bonus"), None)
    assert welcome is None


async def test_list_grants_shows_correct_status(user_client):
    resp = await user_client.get("/v1/usage/grants")
    assert resp.status_code == 200
    body = resp.json()
    for item in body["compute_grants"]:
        assert item["status"] in ("active", "exhausted", "expired")
    for item in body["storage_quota_grants"]:
        assert item["status"] in ("active", "expired")


# ── GET /v1/usage/storage-ledger ──────────────────────────────────────────


async def test_list_storage_ledger_empty(user_client):
    resp = await user_client.get("/v1/usage/storage-ledger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


async def test_list_storage_ledger_with_status_filter(user_client):
    resp = await user_client.get("/v1/usage/storage-ledger", params={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await user_client.get("/v1/usage/storage-ledger", params={"status": "released"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_list_storage_ledger_invalid_status_rejected(user_client):
    resp = await user_client.get("/v1/usage/storage-ledger", params={"status": "invalid"})
    assert resp.status_code == 422


async def test_list_storage_ledger_pagination(user_client):
    resp = await user_client.get("/v1/usage/storage-ledger", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 5
    assert data["offset"] == 0


async def test_list_storage_ledger_released_status_serializes_released(user_client):
    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "user@example.com"))).unique().scalar_one()
        sandbox = Sandbox(
            id="sbreleasedledger001",
            name="released-ledger",
            owner_id=user.id,
            template="aio-sandbox-small",
            k8s_namespace="test",
            status=SandboxStatus.DELETED,
            endpoints={},
        )
        session.add(sandbox)
        session.add(
            StorageLedger(
                id="slreleasedledger001",
                user_id=user.id,
                sandbox_id=sandbox.id,
                size_gib=5,
                storage_state=StorageState.DELETED,
                allocated_at=datetime(2026, 3, 2, 0, 0, 0, tzinfo=UTC),
                released_at=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
                gib_hours_consumed=Decimal("120"),
                last_metered_at=datetime(2026, 3, 3, 0, 0, 0, tzinfo=UTC),
            )
        )
        await session.commit()

    resp = await user_client.get("/v1/usage/storage-ledger", params={"status": "released"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["storage_state"] == "released"
