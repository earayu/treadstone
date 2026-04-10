"""API tests for password reset flow."""

from datetime import timedelta

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.config import settings
from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditEvent
from treadstone.models.password_reset_request_log import PasswordResetRequestLog
from treadstone.models.user import OAuthAccount, User, utc_now
from treadstone.services.email import MemoryBackend, get_email_backend, reset_email_backend

_test_session_factory = None


@pytest.fixture
async def db_session(monkeypatch):
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

    monkeypatch.setattr(settings, "password_reset_request_cooldown_seconds", 60)
    monkeypatch.setattr(settings, "password_reset_ip_hourly_limit", 3)
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_user_db] = override_get_user_db
    app.dependency_overrides[get_user_manager] = override_get_user_manager
    reset_email_backend()
    yield
    app.dependency_overrides.clear()
    reset_email_backend()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


async def _register(client: AsyncClient, email: str, password: str = "Pass123!") -> dict:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


async def _latest_reset_log(email: str) -> PasswordResetRequestLog:
    async with _test_session_factory() as session:
        latest = (
            await session.execute(
                select(PasswordResetRequestLog)
                .where(PasswordResetRequestLog.requested_email == email)
                .order_by(PasswordResetRequestLog.gmt_created.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if latest is None:
        raise AssertionError(f"No password reset log found for {email}")
    return latest


def _memory_backend() -> MemoryBackend:
    backend = get_email_backend()
    assert isinstance(backend, MemoryBackend)
    return backend


@pytest.mark.asyncio
async def test_password_reset_request_for_local_account_sends_email_and_records_audit(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        user = await _register(client, "reset@example.com")

        resp = await client.post("/v1/auth/password-reset/request", json={"email": "reset@example.com"})

    assert resp.status_code == 200
    assert resp.json()["detail"] == "If an account exists, we sent a password reset link."

    backend = _memory_backend()
    assert len(backend.password_reset_emails) == 1
    assert backend.password_reset_emails[0].to == "reset@example.com"
    assert "/auth/reset-password?token=" in backend.password_reset_emails[0].reset_url

    log = await _latest_reset_log("reset@example.com")
    assert log.matched_user_id == user["id"]
    assert log.was_sent is True

    async with _test_session_factory() as session:
        events = (
            (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.password.reset.request")))
            .scalars()
            .all()
        )

    assert len(events) == 1
    assert events[0].target_id == user["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "setup"),
    [
        ("missing@example.com", "missing"),
        ("oauth-only@example.com", "oauth_only"),
        ("disabled@example.com", "disabled"),
    ],
)
async def test_password_reset_request_returns_same_generic_response_for_non_resettable_accounts(
    db_session,
    email,
    setup,
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")

    async with _test_session_factory() as session:
        if setup == "oauth_only":
            session.add(
                User(
                    email=email,
                    hashed_password="hashed",
                    has_local_password=False,
                    is_active=True,
                    is_verified=True,
                    role="rw",
                )
            )
        elif setup == "disabled":
            session.add(
                User(
                    email=email,
                    hashed_password="hashed",
                    has_local_password=True,
                    is_active=False,
                    is_verified=True,
                    role="rw",
                )
            )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/password-reset/request", json={"email": email})

    assert resp.status_code == 200
    assert resp.json()["detail"] == "If an account exists, we sent a password reset link."
    assert _memory_backend().password_reset_emails == []

    log = await _latest_reset_log(email)
    assert log.was_sent is False


@pytest.mark.asyncio
async def test_password_reset_request_enforces_email_cooldown(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _register(client, "cooldown@example.com")

        first = await client.post("/v1/auth/password-reset/request", json={"email": "cooldown@example.com"})
        second = await client.post("/v1/auth/password-reset/request", json={"email": "cooldown@example.com"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "password_reset_rate_limited"


@pytest.mark.asyncio
async def test_password_reset_request_enforces_ip_hourly_limit(db_session, monkeypatch):
    monkeypatch.setattr(settings, "password_reset_ip_hourly_limit", 1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _register(client, "first@example.com")
        await _register(client, "second@example.com")

        first = await client.post("/v1/auth/password-reset/request", json={"email": "first@example.com"})
        second = await client.post("/v1/auth/password-reset/request", json={"email": "second@example.com"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "password_reset_rate_limited"


@pytest.mark.asyncio
async def test_password_reset_confirm_updates_password_and_verifies_email(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        user = await _register(client, "recover@example.com")
        request_resp = await client.post("/v1/auth/password-reset/request", json={"email": "recover@example.com"})
        assert request_resp.status_code == 200

        backend = _memory_backend()
        token = backend.password_reset_emails[0].token

        resp = await client.post(
            "/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "BetterPass123!"},
        )
        login = await client.post("/v1/auth/login", json={"email": "recover@example.com", "password": "BetterPass123!"})

    assert resp.status_code == 200
    assert resp.json()["detail"] == "Password reset successful"
    assert login.status_code == 200

    async with _test_session_factory() as session:
        db_user = (await session.execute(select(User).where(User.id == user["id"]))).unique().scalar_one()
        events = (
            (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.password.reset")))
            .scalars()
            .all()
        )

    assert db_user.is_verified is True
    assert len(events) == 1
    assert events[0].target_id == user["id"]


@pytest.mark.asyncio
async def test_password_reset_confirm_rejects_invalid_token_and_records_failure(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/password-reset/confirm",
            json={"token": "bad-token", "new_password": "BetterPass123!"},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "password_reset_token_invalid"

    async with _test_session_factory() as session:
        events = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == "auth.password.reset",
                        AuditEvent.result == "failure",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(events) == 1
    assert events[0].error_code == "password_reset_token_invalid"


@pytest.mark.asyncio
async def test_password_reset_confirm_invalidates_old_token_after_success(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _register(client, "stale@example.com")
        await client.post("/v1/auth/password-reset/request", json={"email": "stale@example.com"})

        backend = _memory_backend()
        token = backend.password_reset_emails[0].token

        first = await client.post(
            "/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "FreshPass123!"},
        )
        second = await client.post(
            "/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "AnotherPass123!"},
        )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "password_reset_token_invalid"


@pytest.mark.asyncio
async def test_password_reset_request_cooldown_expires_after_window(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _register(client, "window@example.com")
        first = await client.post("/v1/auth/password-reset/request", json={"email": "window@example.com"})
        assert first.status_code == 200

    async with _test_session_factory() as session:
        log = (
            await session.execute(
                select(PasswordResetRequestLog)
                .where(PasswordResetRequestLog.requested_email == "window@example.com")
                .order_by(PasswordResetRequestLog.gmt_created.desc())
                .limit(1)
            )
        ).scalar_one()
        log.gmt_created = utc_now() - timedelta(seconds=120)
        session.add(log)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        second = await client.post("/v1/auth/password-reset/request", json={"email": "window@example.com"})

    assert second.status_code == 200
