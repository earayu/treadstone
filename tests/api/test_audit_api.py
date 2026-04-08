from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditActorType, AuditEvent, AuditResult
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


@pytest.mark.asyncio
async def test_audit_filter_options_returns_distinct_values(admin_client):
    await admin_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "filter-opt-box"},
    )

    response = await admin_client.get("/v1/audit/filter-options")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["actions"], list)
    assert isinstance(data["target_types"], list)
    assert isinstance(data["results"], list)
    assert "sandbox.create" in data["actions"]
    assert "sandbox" in data["target_types"]
    assert "success" in data["results"]


@pytest.mark.asyncio
async def test_audit_filter_options_requires_admin(member_client):
    response = await member_client.get("/v1/audit/filter-options")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_events_filter_by_actor_email(admin_client):
    await admin_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "actor-email-box"},
    )

    response = await admin_client.get("/v1/audit/events", params={"actor_email": "admin@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["actor_user_id"] is not None for item in data["items"])


@pytest.mark.asyncio
async def test_audit_events_filter_by_actor_email_not_found_returns_empty(admin_client):
    response = await admin_client.get("/v1/audit/events", params={"actor_email": "nobody@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_audit_events_filter_by_actor_email_is_case_insensitive_and_trimmed(admin_client):
    await admin_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "actor-email-normalized-box"},
    )

    response = await admin_client.get("/v1/audit/events", params={"actor_email": "  ADMIN@EXAMPLE.COM  "})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["actor_user_id"] is not None for item in data["items"])


@pytest.mark.asyncio
async def test_audit_events_reject_inverted_time_range(admin_client):
    response = await admin_client.get(
        "/v1/audit/events",
        params={
            "since": "2026-04-08T12:00:00Z",
            "until": "2026-04-08T11:59:59Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_audit_events_actor_email_and_actor_user_id_apply_intersection(admin_client):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon_client:
        await anon_client.post("/v1/auth/register", json={"email": "member@example.com", "password": "Pass123!"})

    async with _test_session_factory() as session:
        member = (await session.execute(select(User).where(User.email == "member@example.com"))).unique().scalar_one()
        session.add(
            AuditEvent(
                id="audactorintersection0001",
                created_at=datetime(2026, 4, 3, 0, 0, tzinfo=UTC),
                actor_type=AuditActorType.USER.value,
                actor_user_id=member.id,
                action="sandbox.create",
                target_type="sandbox",
                target_id="sb-member",
                result=AuditResult.SUCCESS.value,
                event_metadata={},
            )
        )
        await session.commit()

    response = await admin_client.get(
        "/v1/audit/events",
        params={"actor_email": "admin@example.com", "actor_user_id": member.id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_audit_events_pagination_is_stable_for_same_created_at(admin_client):
    async with _test_session_factory() as session:
        for event_id in ("audsamecreatedat0002", "audsamecreatedat0001", "audsamecreatedat0003"):
            session.add(
                AuditEvent(
                    id=event_id,
                    created_at=datetime(2026, 4, 3, 0, 0, tzinfo=UTC),
                    actor_type=AuditActorType.SYSTEM.value,
                    action="metering.monthly_reset",
                    target_type="user",
                    result=AuditResult.SUCCESS.value,
                    event_metadata={},
                )
            )
        await session.commit()

    page_one = await admin_client.get(
        "/v1/audit/events",
        params={"action": "metering.monthly_reset", "limit": 2, "offset": 0},
    )
    page_two = await admin_client.get(
        "/v1/audit/events",
        params={"action": "metering.monthly_reset", "limit": 2, "offset": 2},
    )

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert [item["id"] for item in page_one.json()["items"]] == ["audsamecreatedat0003", "audsamecreatedat0002"]
    assert [item["id"] for item in page_two.json()["items"]] == ["audsamecreatedat0001"]
