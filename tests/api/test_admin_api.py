"""Tests for the Admin API (/v1/admin/*).

Covers F25–F28: Admin read/write endpoints for managing metering.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.metering import TierTemplate
from treadstone.models.user import OAuthAccount, User
from treadstone.models.user_feedback import UserFeedback  # noqa: F401 — register model for SQLite metadata
from treadstone.models.waitlist import WaitlistApplication  # noqa: F401 — register model for SQLite metadata

_test_session_factory: async_sessionmaker | None = None


async def _seed_tier_templates(session: AsyncSession) -> None:
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
        TierTemplate(
            tier_name="ultra",
            compute_units_monthly=Decimal("300"),
            storage_capacity_gib=20,
            max_concurrent_running=5,
            max_sandbox_duration_seconds=28800,
            allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium", "aio-sandbox-large"],
            grace_period_seconds=3600,
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
async def admin_client(db_session):
    """First registered user becomes admin. Returns (client, user_id)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await client.post("/v1/auth/register", json={"email": "admin@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "admin@example.com", "password": "Pass123!"})
        client._admin_user_id = reg.json()["id"]  # type: ignore[attr-defined]
        yield client


@pytest.fixture
async def member_client(db_session):
    """Second registered user is a non-admin member."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin@example.com", "password": "Pass123!"})
        reg = await client.post("/v1/auth/register", json={"email": "member@example.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "member@example.com", "password": "Pass123!"})
        client._member_user_id = reg.json()["id"]  # type: ignore[attr-defined]
        yield client


@pytest.fixture
async def anon_client(db_session):
    """Unauthenticated client (same DB as admin tests)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _get_user_id(client: AsyncClient) -> str:
    return client._admin_user_id  # type: ignore[attr-defined]


# ── GET /v1/admin/tier-templates ─────────────────────────────────────────────


async def test_list_tier_templates(admin_client):
    resp = await admin_client.get("/v1/admin/tier-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3

    tiers = [t["tier"] for t in data["items"]]
    assert "free" in tiers
    assert "pro" in tiers
    assert "ultra" in tiers


async def test_list_tier_templates_requires_admin(member_client):
    resp = await member_client.get("/v1/admin/tier-templates")
    assert resp.status_code == 403


# ── PATCH /v1/admin/tier-templates/{tier_name} ──────────────────────────────


async def test_update_tier_template(admin_client):
    resp = await admin_client.patch(
        "/v1/admin/tier-templates/pro",
        json={"compute_units_monthly": 150, "apply_to_existing": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compute_units_monthly"] == 150.0
    assert data["users_affected"] == 0


async def test_update_tier_template_not_found(admin_client):
    resp = await admin_client.patch(
        "/v1/admin/tier-templates/nonexistent",
        json={"compute_units_monthly": 150},
    )
    assert resp.status_code == 404


async def test_update_tier_template_apply_to_existing(admin_client):
    user_id = _get_user_id(admin_client)

    await admin_client.patch(f"/v1/admin/users/{user_id}/plan", json={"tier": "pro"})

    resp = await admin_client.patch(
        "/v1/admin/tier-templates/pro",
        json={"compute_units_monthly": 200, "apply_to_existing": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["compute_units_monthly"] == 200.0
    assert data["users_affected"] >= 1

    plan_resp = await admin_client.get("/v1/usage/plan")
    assert plan_resp.json()["compute_units_monthly_limit"] == 200.0


async def test_update_tier_template_apply_to_existing_skips_overridden(admin_client):
    user_id = _get_user_id(admin_client)

    await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"tier": "pro", "overrides": {"compute_units_monthly_limit": 999}},
    )

    resp = await admin_client.patch(
        "/v1/admin/tier-templates/pro",
        json={"compute_units_monthly": 200, "apply_to_existing": True},
    )
    assert resp.status_code == 200
    assert resp.json()["users_affected"] == 0

    plan_resp = await admin_client.get("/v1/usage/plan")
    assert plan_resp.json()["compute_units_monthly_limit"] == 999.0


async def test_update_tier_template_requires_at_least_one_field(admin_client):
    resp = await admin_client.patch(
        "/v1/admin/tier-templates/pro",
        json={"apply_to_existing": False},
    )
    assert resp.status_code == 422


# ── GET /v1/admin/users/{user_id}/usage ──────────────────────────────────────


async def test_admin_get_user_usage(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.get(f"/v1/admin/users/{user_id}/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"
    assert "compute" in data
    assert "storage" in data


async def test_admin_get_user_usage_not_found(admin_client):
    resp = await admin_client.get("/v1/admin/users/nonexistent_user/usage")
    assert resp.status_code == 404


async def test_admin_get_user_usage_requires_admin(member_client):
    resp = await member_client.get("/v1/admin/users/some_user/usage")
    assert resp.status_code == 403


# ── PATCH /v1/admin/users/{user_id}/plan ─────────────────────────────────────


async def test_admin_update_user_plan_change_tier(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"tier": "pro"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "pro"
    assert data["compute_units_monthly_limit"] == 100.0
    assert data["max_concurrent_running"] == 3


async def test_admin_update_user_plan_with_overrides(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"tier": "pro", "overrides": {"compute_units_monthly_limit": 200}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "pro"
    assert data["compute_units_monthly_limit"] == 200.0
    assert data["overrides"]["compute_units_monthly_limit"] == 200


async def test_admin_update_user_plan_overrides_only(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"overrides": {"max_concurrent_running": 10}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_concurrent_running"] == 10


async def test_admin_update_user_plan_requires_at_least_one_field(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={},
    )
    assert resp.status_code == 422


async def test_admin_update_user_plan_invalid_tier(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"tier": "nonexistent_tier"},
    )
    assert resp.status_code == 404


async def test_admin_update_user_plan_invalid_override_key(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.patch(
        f"/v1/admin/users/{user_id}/plan",
        json={"overrides": {"invalid_key": 999}},
    )
    assert resp.status_code == 422


# ── POST /v1/admin/users/{user_id}/compute-grants | storage-grants ───────────


async def test_admin_create_grant(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        f"/v1/admin/users/{user_id}/compute-grants",
        json={
            "amount": 100,
            "grant_type": "admin_grant",
            "reason": "Test grant",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["original_amount"] == 100.0
    assert data["remaining_amount"] == 100.0
    assert data["grant_type"] == "admin_grant"
    assert data["reason"] == "Test grant"
    assert data["granted_by"] is not None


async def test_admin_create_grant_with_expiry(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        f"/v1/admin/users/{user_id}/storage-grants",
        json={
            "size_gib": 5,
            "grant_type": "admin_grant",
            "expires_at": "2027-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["size_gib"] == 5
    assert data["expires_at"] is not None


async def test_admin_create_grant_user_not_found(admin_client):
    resp = await admin_client.post(
        "/v1/admin/users/nonexistent_user/compute-grants",
        json={"amount": 50, "grant_type": "admin_grant"},
    )
    assert resp.status_code == 404


async def test_admin_create_compute_grant_negative_amount_rejected(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        f"/v1/admin/users/{user_id}/compute-grants",
        json={"amount": -5, "grant_type": "admin_grant"},
    )
    assert resp.status_code == 422


async def test_admin_create_grant_zero_amount_rejected(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        f"/v1/admin/users/{user_id}/compute-grants",
        json={"amount": 0, "grant_type": "admin_grant"},
    )
    assert resp.status_code == 422


async def test_admin_grant_shows_in_usage(admin_client):
    user_id = _get_user_id(admin_client)
    await admin_client.post(
        f"/v1/admin/users/{user_id}/compute-grants",
        json={"amount": 200, "grant_type": "admin_grant"},
    )
    grants_resp = await admin_client.get("/v1/usage/grants")
    assert grants_resp.status_code == 200
    admin_grants = [g for g in grants_resp.json()["compute_grants"] if g["grant_type"] == "admin_grant"]
    assert any(g["remaining_amount"] >= 200.0 for g in admin_grants)


# ── POST /v1/admin/compute-grants/batch ───────────────────────────────────────


async def test_batch_grants_success(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        "/v1/admin/compute-grants/batch",
        json={
            "user_ids": [user_id],
            "amount": 25,
            "grant_type": "campaign",
            "campaign_id": "test_campaign",
            "reason": "Batch test",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requested"] == 1
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert data["results"][0]["status"] == "success"
    assert data["results"][0]["grant_id"] is not None


async def test_batch_grants_partial_failure(admin_client):
    user_id = _get_user_id(admin_client)
    resp = await admin_client.post(
        "/v1/admin/compute-grants/batch",
        json={
            "user_ids": [user_id, "nonexistent_user"],
            "amount": 25,
            "grant_type": "campaign",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requested"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1

    success = next(r for r in data["results"] if r["status"] == "success")
    assert success["user_id"] == user_id

    failure = next(r for r in data["results"] if r["status"] == "failed")
    assert failure["user_id"] == "nonexistent_user"
    assert failure["error"] == "User not found"


async def test_batch_grants_requires_admin(member_client):
    resp = await member_client.post(
        "/v1/admin/compute-grants/batch",
        json={
            "user_ids": ["anyone"],
            "amount": 25,
            "grant_type": "campaign",
        },
    )
    assert resp.status_code == 403


async def test_batch_grants_empty_user_ids_rejected(admin_client):
    resp = await admin_client.post(
        "/v1/admin/compute-grants/batch",
        json={
            "user_ids": [],
            "amount": 25,
            "grant_type": "campaign",
        },
    )
    assert resp.status_code == 422


# ── GET /v1/admin/users/lookup-by-email ──────────────────────────────────────


async def test_lookup_user_by_email(admin_client):
    resp = await admin_client.get("/v1/admin/users/lookup-by-email", params={"email": "admin@example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@example.com"
    assert data["user_id"] == _get_user_id(admin_client)


async def test_lookup_user_by_email_not_found(admin_client):
    resp = await admin_client.get("/v1/admin/users/lookup-by-email", params={"email": "nobody@example.com"})
    assert resp.status_code == 404


async def test_lookup_user_by_email_requires_admin(member_client):
    resp = await member_client.get("/v1/admin/users/lookup-by-email", params={"email": "admin@example.com"})
    assert resp.status_code == 403


# ── POST /v1/admin/users/resolve-emails ──────────────────────────────────────


async def test_resolve_emails_success(admin_client):
    resp = await admin_client.post("/v1/admin/users/resolve-emails", json={"emails": ["admin@example.com"]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["email"] == "admin@example.com"
    assert data["results"][0]["user_id"] == _get_user_id(admin_client)
    assert data["results"][0]["error"] is None


async def test_resolve_emails_partial_not_found(admin_client):
    resp = await admin_client.post(
        "/v1/admin/users/resolve-emails",
        json={"emails": ["admin@example.com", "nobody@example.com"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2

    found = next(r for r in data["results"] if r["email"] == "admin@example.com")
    assert found["user_id"] is not None
    assert found["error"] is None

    not_found = next(r for r in data["results"] if r["email"] == "nobody@example.com")
    assert not_found["user_id"] is None
    assert not_found["error"] == "User not found"


async def test_resolve_emails_requires_admin(member_client):
    resp = await member_client.post("/v1/admin/users/resolve-emails", json={"emails": ["admin@example.com"]})
    assert resp.status_code == 403


# ── Waitlist (public POST + admin list/patch) ────────────────────────────────


_WAITLIST_BODY = {
    "email": "guest@example.com",
    "name": "Guest User",
    "target_tier": "pro",
}


async def test_post_waitlist_without_auth(anon_client):
    resp = await anon_client.post("/v1/waitlist", json=_WAITLIST_BODY)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "guest@example.com"
    assert data["status"] == "pending"
    assert "user_id" not in data
    assert data.get("github_or_portfolio_url") is None


async def test_post_waitlist_accepts_https_portfolio_url(anon_client):
    resp = await anon_client.post(
        "/v1/waitlist",
        json={
            **_WAITLIST_BODY,
            "email": "withlink@example.com",
            "github_or_portfolio_url": "https://github.com/example",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["github_or_portfolio_url"] == "https://github.com/example"


async def test_post_waitlist_rejects_non_https_portfolio_url(anon_client):
    resp = await anon_client.post(
        "/v1/waitlist",
        json={
            **_WAITLIST_BODY,
            "email": "badlink@example.com",
            "github_or_portfolio_url": "http://github.com/example",
        },
    )
    assert resp.status_code == 422


async def test_post_waitlist_allows_multiple_same_email_tier(anon_client):
    body = {**_WAITLIST_BODY, "email": "repeat@example.com"}
    r1 = await anon_client.post("/v1/waitlist", json=body)
    r2 = await anon_client.post("/v1/waitlist", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


async def test_post_waitlist_does_not_link_existing_user_id(db_session, admin_client, anon_client):
    r = await anon_client.post(
        "/v1/waitlist",
        json={
            "email": "admin@example.com",
            "name": "Admin Applicant",
            "target_tier": "ultra",
        },
    )
    assert r.status_code == 201
    assert "user_id" not in r.json()

    async with _test_session_factory() as session:
        row = (
            await session.execute(select(WaitlistApplication).where(WaitlistApplication.email == "admin@example.com"))
        ).scalar_one()
        assert row.user_id is None


async def test_patch_waitlist_only_from_pending(admin_client, anon_client):
    r = await anon_client.post("/v1/waitlist", json={**_WAITLIST_BODY, "email": "pendingflow@example.com"})
    assert r.status_code == 201
    app_id = r.json()["id"]

    ok = await admin_client.patch(f"/v1/admin/waitlist/{app_id}", json={"status": "approved"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved"

    conflict = await admin_client.patch(f"/v1/admin/waitlist/{app_id}", json={"status": "rejected"})
    assert conflict.status_code == 409
    msg = conflict.json()["error"]["message"].lower()
    assert "pending" in msg or "already" in msg


async def test_list_waitlist_requires_admin(member_client, anon_client):
    await anon_client.post("/v1/waitlist", json=_WAITLIST_BODY)
    resp = await member_client.get("/v1/admin/waitlist")
    assert resp.status_code == 403


# ── Support feedback (POST /v1/support/feedback, GET /v1/admin/support/feedback) ─


async def test_create_feedback_requires_auth(anon_client):
    resp = await anon_client.post("/v1/support/feedback", json={"body": "hello"})
    assert resp.status_code == 401


async def test_create_feedback_member(member_client):
    resp = await member_client.post("/v1/support/feedback", json={"body": "  My issue  "})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"].startswith("fb")


async def test_create_feedback_empty_body(member_client):
    resp = await member_client.post("/v1/support/feedback", json={"body": "   "})
    assert resp.status_code == 422


async def test_create_feedback_body_too_long(member_client):
    resp = await member_client.post("/v1/support/feedback", json={"body": "x" * 10_001})
    assert resp.status_code == 422


async def test_list_feedback_admin(admin_client):
    await admin_client.post("/v1/support/feedback", json={"body": "from admin user feedback"})
    resp = await admin_client.get("/v1/admin/support/feedback")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("from admin user feedback" in item["body"] for item in data["items"])


async def test_list_feedback_forbidden_member(member_client):
    resp = await member_client.get("/v1/admin/support/feedback")
    assert resp.status_code == 403


async def test_list_feedback_filter_by_email(admin_client, member_client):
    await member_client.post("/v1/support/feedback", json={"body": "email filter marker"})
    resp = await admin_client.get("/v1/admin/support/feedback", params={"email": "member@example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("email filter marker" in item["body"] for item in data["items"])

    resp_empty = await admin_client.get("/v1/admin/support/feedback", params={"email": "nomatch@example.com"})
    assert resp_empty.status_code == 200
    assert resp_empty.json()["total"] == 0
