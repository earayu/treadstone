from datetime import UTC, datetime

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_jwt_strategy, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditEvent
from treadstone.models.user import OAuthAccount, User

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
    assert data["is_verified"] is True

    async with _test_session_factory() as session:
        event = (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.register"))).scalar_one()

    assert event.target_id == data["id"]
    assert event.actor_user_id == data["id"]


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

    async with _test_session_factory() as session:
        events = (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login"))).scalars().all()

    assert len(events) == 1
    assert events[0].result == "success"


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "x@b.com", "password": "Pass123!"})
        resp = await client.post("/v1/auth/login", json={"email": "x@b.com", "password": "WRONG"})
    assert resp.status_code == 400

    async with _test_session_factory() as session:
        events = (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.login"))).scalars().all()

    assert len(events) == 1
    assert events[0].result == "failure"
    assert events[0].error_code == "bad_request"


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
    assert resp.json()["has_local_password"] is True
    assert resp.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_set_password_rejects_existing_local_password_user(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "local@b.com", "password": "Pass123!"})
        response = await client.post("/v1/auth/set-password", json={"new_password": "NewPass123!"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
    assert "change-password" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_change_password_rejects_user_without_local_password(db_session):
    async with _test_session_factory() as session:
        user = User(
            email="oauth-only@example.com",
            hashed_password="hashed",
            has_local_password=False,
            is_active=True,
            is_verified=True,
            role="rw",
        )
        session.add(user)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_resp = await client.post(
            "/v1/auth/login",
            json={"email": "oauth-only@example.com", "password": "wrong"},
        )
        assert login_resp.status_code == 400

        async with _test_session_factory() as session:
            oauth_user = (
                (await session.execute(select(User).where(User.email == "oauth-only@example.com")))
                .unique()
                .scalar_one()
            )

        session_cookie = await get_jwt_strategy().write_token(oauth_user)
        client.cookies.set("session", session_cookie)

        response = await client.post(
            "/v1/auth/change-password",
            json={"old_password": "anything", "new_password": "NewPass123!"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
    assert "set-password" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_invite_endpoint_is_removed(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/invite", json={"email": "member@example.com", "role": "ro"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_disable_user(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin@test.com", "password": "Pass123!"})
        login = await client.post("/v1/auth/login", json={"email": "admin@test.com", "password": "Pass123!"})
        admin_cookies = login.cookies

    async with _test_session_factory() as session:
        target = User(
            email="target@test.com",
            hashed_password="hashed",
            has_local_password=True,
            is_active=True,
            is_verified=True,
            role="rw",
        )
        session.add(target)
        await session.commit()
        target_id = target.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/v1/auth/users/{target_id}/status",
            json={"is_active": False},
            cookies=admin_cookies,
        )
    assert resp.status_code == 200
    assert "disabled" in resp.json()["detail"].lower()

    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.id == target_id))).unique().scalar_one()
    assert user.is_active is False

    async with _test_session_factory() as session:
        event = (
            await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.user.status_change"))
        ).scalar_one()
    assert event.target_id == target_id


@pytest.mark.asyncio
async def test_admin_enable_user(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin2@test.com", "password": "Pass123!"})
        login = await client.post("/v1/auth/login", json={"email": "admin2@test.com", "password": "Pass123!"})
        admin_cookies = login.cookies

    async with _test_session_factory() as session:
        target = User(
            email="disabled@test.com",
            hashed_password="hashed",
            has_local_password=True,
            is_active=False,
            is_verified=True,
            role="rw",
        )
        session.add(target)
        await session.commit()
        target_id = target.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/v1/auth/users/{target_id}/status",
            json={"is_active": True},
            cookies=admin_cookies,
        )
    assert resp.status_code == 200
    assert "enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await client.post("/v1/auth/register", json={"email": "selfadmin@test.com", "password": "Pass123!"})
        admin_id = reg.json()["id"]
        login = await client.post("/v1/auth/login", json={"email": "selfadmin@test.com", "password": "Pass123!"})
        admin_cookies = login.cookies

        resp = await client.patch(
            f"/v1/auth/users/{admin_id}/status",
            json={"is_active": False},
            cookies=admin_cookies,
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin3@test.com", "password": "Pass123!"})
        login = await client.post("/v1/auth/login", json={"email": "admin3@test.com", "password": "Pass123!"})
        admin_cookies = login.cookies

    async with _test_session_factory() as session:
        from fastapi_users.password import PasswordHelper

        ph = PasswordHelper()
        target = User(
            email="willbe-disabled@test.com",
            hashed_password=ph.hash("Pass123!"),
            has_local_password=True,
            is_active=True,
            is_verified=True,
            role="rw",
        )
        session.add(target)
        await session.commit()
        target_id = target.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch(
            f"/v1/auth/users/{target_id}/status",
            json={"is_active": False},
            cookies=admin_cookies,
        )

        resp = await client.post(
            "/v1/auth/login",
            json={"email": "willbe-disabled@test.com", "password": "Pass123!"},
        )
    assert resp.status_code == 403
    assert "disabled" in resp.json()["error"]["message"].lower()

    async with _test_session_factory() as session:
        login_events = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == "auth.login",
                        AuditEvent.error_code == "account_disabled",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(login_events) == 1


@pytest.mark.asyncio
async def test_list_users_includes_is_active(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "lister@test.com", "password": "Pass123!"})
        login = await client.post("/v1/auth/login", json={"email": "lister@test.com", "password": "Pass123!"})
        resp = await client.get("/v1/auth/users", cookies=login.cookies)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert "is_active" in items[0]


@pytest.mark.asyncio
async def test_list_users_admin_newest_first_and_paginated(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "admin-order@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "second-user@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "third-user@test.com", "password": "Pass123!"})
        login = await client.post(
            "/v1/auth/login",
            json={"email": "admin-order@test.com", "password": "Pass123!"},
        )
        cookies = login.cookies

        resp = await client.get("/v1/auth/users", cookies=cookies, params={"limit": 10, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        emails = [i["email"] for i in body["items"]]
        assert emails[0] == "third-user@test.com"
        assert emails[1] == "second-user@test.com"
        assert emails[2] == "admin-order@test.com"

        page1 = await client.get("/v1/auth/users", cookies=cookies, params={"limit": 1, "offset": 0})
        assert page1.json()["items"][0]["email"] == "third-user@test.com"
        page2 = await client.get("/v1/auth/users", cookies=cookies, params={"limit": 1, "offset": 1})
        assert page2.json()["items"][0]["email"] == "second-user@test.com"


@pytest.mark.asyncio
async def test_list_users_admin_email_filter(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "filter-admin@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "alice.unique@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "bob.unique@test.com", "password": "Pass123!"})
        login = await client.post(
            "/v1/auth/login",
            json={"email": "filter-admin@test.com", "password": "Pass123!"},
        )
        cookies = login.cookies

        resp = await client.get("/v1/auth/users", cookies=cookies, params={"email": "alice.unique"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "alice.unique@test.com"

        resp_all = await client.get("/v1/auth/users", cookies=cookies, params={"email": "unique@"})
        assert resp_all.json()["total"] == 2


@pytest.mark.asyncio
async def test_list_users_non_admin_respects_offset(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "self-only@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "member-only@test.com", "password": "Pass123!"})
        login = await client.post("/v1/auth/login", json={"email": "member-only@test.com", "password": "Pass123!"})

        resp = await client.get("/v1/auth/users", cookies=login.cookies, params={"limit": 1, "offset": 1})

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_list_users_admin_pagination_is_stable_when_timestamps_tie(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "stable-admin@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "stable-a@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/register", json={"email": "stable-b@test.com", "password": "Pass123!"})
        login = await client.post(
            "/v1/auth/login",
            json={"email": "stable-admin@test.com", "password": "Pass123!"},
        )
        cookies = login.cookies

    tied_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    async with _test_session_factory() as session:
        users = (
            (
                await session.execute(
                    select(User).where(
                        User.email.in_(["stable-admin@test.com", "stable-a@test.com", "stable-b@test.com"])
                    )
                )
            )
            .unique()
            .scalars()
            .all()
        )
        for user in users:
            if user.email == "stable-admin@test.com":
                user.gmt_created = datetime(2025, 1, 1, tzinfo=UTC)
            else:
                user.gmt_created = tied_created_at
            session.add(user)
        await session.commit()
        tied_ids = {user.email: user.id for user in users if user.email != "stable-admin@test.com"}

    expected_first_email = max(tied_ids.items(), key=lambda item: item[1])[0]
    expected_second_email = min(tied_ids.items(), key=lambda item: item[1])[0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_page = await client.get("/v1/auth/users", cookies=cookies, params={"limit": 1, "offset": 0})
        second_page = await client.get("/v1/auth/users", cookies=cookies, params={"limit": 1, "offset": 1})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.json()["items"][0]["email"] == expected_first_email
    assert second_page.json()["items"][0]["email"] == expected_second_email
