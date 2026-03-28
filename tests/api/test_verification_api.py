"""API tests for email verification flow."""

from datetime import timedelta

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditEvent
from treadstone.models.email_verification_log import EmailVerificationLog
from treadstone.models.user import OAuthAccount, User, utc_now
from treadstone.services.email import reset_email_backend

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
    reset_email_backend()
    yield
    app.dependency_overrides.clear()
    reset_email_backend()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


async def _register(client: AsyncClient, email: str = "test@example.com", password: str = "Pass123!") -> dict:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


async def _login(client: AsyncClient, email: str = "test@example.com", password: str = "Pass123!") -> None:
    resp = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


async def _get_verification_token(email: str) -> str:
    """Fetch the latest verification token from the DB."""
    async with _test_session_factory() as session:
        latest = (
            await session.execute(
                select(EmailVerificationLog)
                .where(EmailVerificationLog.email == email)
                .order_by(EmailVerificationLog.gmt_created.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if latest is None:
        raise AssertionError(f"No verification token found for {email}")
    return latest.token


async def test_register_first_user_is_auto_verified(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = await _register(client, "admin@example.com")

    assert data["is_verified"] is True
    assert data["verification_email_sent"] is False
    assert data["role"] == "admin"


async def test_register_non_first_user_is_unverified(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        data = await _register(client, "second@example.com")

    assert data["is_verified"] is False
    assert data["verification_email_sent"] is True


async def test_register_triggers_verification_email(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "second@example.com")

    async with _test_session_factory() as session:
        logs = (await session.execute(select(EmailVerificationLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].email == "second@example.com"
    assert "verify-email?token=" in logs[0].verify_url


async def test_confirm_verification_succeeds(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        token = await _get_verification_token("user@example.com")

        resp = await client.post("/v1/auth/verification/confirm", json={"token": token})
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Email verified"


async def test_confirm_verification_records_audit_event(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        data = await _register(client, "user@example.com")
        token = await _get_verification_token("user@example.com")

        await client.post("/v1/auth/verification/confirm", json={"token": token})

    async with _test_session_factory() as session:
        events = (await session.execute(select(AuditEvent).where(AuditEvent.action == "auth.verify"))).scalars().all()

    assert len(events) == 1
    assert events[0].target_id == data["id"]


async def test_confirm_invalid_token_returns_400(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/verification/confirm", json={"token": "invalid-token"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "email_verification_token_invalid"


async def test_confirm_already_verified_returns_400(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        token = await _get_verification_token("user@example.com")

        await client.post("/v1/auth/verification/confirm", json={"token": token})
        resp = await client.post("/v1/auth/verification/confirm", json={"token": token})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "email_already_verified"


async def test_get_user_includes_is_verified(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        await _login(client, "user@example.com")

        resp = await client.get("/v1/auth/user")
    assert resp.status_code == 200
    assert resp.json()["is_verified"] is False


async def test_resend_verification_succeeds(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        await _login(client, "user@example.com")

        async with _test_session_factory() as session:
            log = (
                await session.execute(
                    select(EmailVerificationLog).where(EmailVerificationLog.email == "user@example.com")
                )
            ).scalar_one()
            log.gmt_created = utc_now() - timedelta(seconds=120)
            session.add(log)
            await session.commit()

        resp = await client.post("/v1/auth/verification/request")
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Verification email sent"

    async with _test_session_factory() as session:
        logs = (
            (
                await session.execute(
                    select(EmailVerificationLog).where(EmailVerificationLog.email == "user@example.com")
                )
            )
            .scalars()
            .all()
        )
    assert len(logs) == 2


async def test_resend_verification_already_verified_returns_400(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _login(client, "admin@example.com")

        resp = await client.post("/v1/auth/verification/request")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "email_already_verified"


async def test_unverified_user_cannot_create_sandbox(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        await _login(client, "user@example.com")

        resp = await client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "email_verification_required"

    async with _test_session_factory() as session:
        events = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == "sandbox.create",
                        AuditEvent.error_code == "email_verification_required",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(events) == 1


async def test_verified_user_can_create_sandbox(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        await _login(client, "user@example.com")

        token = await _get_verification_token("user@example.com")
        await client.post("/v1/auth/verification/confirm", json={"token": token})

        resp = await client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny"})
    assert resp.status_code == 202


async def test_full_verification_flow(db_session):
    """Register -> unverified -> capture token -> confirm -> verified -> create sandbox."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")

        reg_data = await _register(client, "user@example.com")
        assert reg_data["is_verified"] is False
        assert reg_data["verification_email_sent"] is True

        await _login(client, "user@example.com")

        user_resp = await client.get("/v1/auth/user")
        assert user_resp.json()["is_verified"] is False

        token = await _get_verification_token("user@example.com")
        confirm_resp = await client.post("/v1/auth/verification/confirm", json={"token": token})
        assert confirm_resp.status_code == 200

        user_resp = await client.get("/v1/auth/user")
        assert user_resp.json()["is_verified"] is True

        sandbox_resp = await client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny"})
        assert sandbox_resp.status_code == 202


async def test_admin_can_get_verification_token_by_email(db_session):
    """Admin endpoint returns the latest verification token for a given email."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_data = await _register(client, "admin@example.com")
        assert admin_data["role"] == "admin"

        await _register(client, "user@example.com")

        await _login(client, "admin@example.com")
        resp = await client.get("/v1/admin/verification-token-by-email?email=user@example.com")

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert "token" in data
    assert len(data["token"]) > 0


async def test_non_admin_cannot_access_verification_token(db_session):
    """Non-admin user gets 403 when trying to access admin verification endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "admin@example.com")
        await _register(client, "user@example.com")

        await _login(client, "user@example.com")
        resp = await client.get("/v1/admin/verification-token-by-email?email=user@example.com")

    assert resp.status_code == 403


async def test_confirm_invalid_token_records_audit_event(db_session):
    """Failed verification attempt is recorded in audit log."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/verification/confirm", json={"token": "bad-token"})
    assert resp.status_code == 400

    async with _test_session_factory() as session:
        events = (
            (
                await session.execute(
                    select(AuditEvent).where(
                        AuditEvent.action == "auth.verify",
                        AuditEvent.result == "failure",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(events) == 1
    assert events[0].error_code == "email_verification_token_invalid"


async def test_resend_verification_cooldown_rejects(db_session):
    """Resend within 60 seconds is rejected with 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _register(client, "first@example.com")
        await _register(client, "user@example.com")
        await _login(client, "user@example.com")

        resp = await client.post("/v1/auth/verification/request")
    assert resp.status_code == 400
    assert "wait" in resp.json()["error"]["message"].lower()
