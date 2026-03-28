from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.api import auth as auth_api
from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User
from treadstone.services import browser_login as browser_login_service

_test_session_factory = None


class FakeOAuthClient:
    def __init__(self, name: str, account_id: str = "acct-123", account_email: str | None = "user@example.com") -> None:
        self.name = name
        self.account_id = account_id
        self.account_email = account_email
        self.authorization_calls: list[tuple[str, str, list[str] | None]] = []
        self.access_token_calls: list[tuple[str, str, str | None]] = []

    async def get_authorization_url(self, redirect_url: str, state: str, scopes: list[str] | None = None) -> str:
        self.authorization_calls.append((redirect_url, state, scopes))
        return f"https://provider.example/{self.name}/authorize?state={state}"

    async def get_access_token(self, code: str, redirect_url: str, code_verifier: str | None = None) -> dict:
        self.access_token_calls.append((code, redirect_url, code_verifier))
        return {"access_token": f"{self.name}-access-token"}

    async def get_id_email(self, token: str) -> tuple[str, str | None]:
        return self.account_id, self.account_email


class FakeGitHubOAuthClient(FakeOAuthClient):
    def __init__(
        self,
        account_id: str = "gh-123",
        account_email: str | None = "user@example.com",
        emails: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__("github", account_id=account_id, account_email=account_email)
        self.emails = emails or [
            {"email": account_email, "primary": True, "verified": True},
        ]

    async def get_profile(self, token: str) -> dict[str, object]:
        return {"id": self.account_id, "email": self.account_email}

    async def get_emails(self, token: str) -> list[dict[str, object]]:
        return self.emails


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


def _extract_state(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


def _enable_browser_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    monkeypatch.setattr(auth_api.settings, "sandbox_domain", "sandbox.localhost")
    monkeypatch.setattr(browser_login_service.settings, "sandbox_domain", "sandbox.localhost")


@pytest.mark.asyncio
async def test_google_authorize_redirects_to_provider_and_sets_flow_cookies(db_session, monkeypatch):
    _enable_browser_flow(monkeypatch)
    client = FakeOAuthClient("google")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        response = await http_client.get(
            "/v1/auth/google/authorize",
            params={"return_to": "https://sandbox-demo.sandbox.localhost/"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"].startswith("https://provider.example/google/authorize")
    assert client.authorization_calls == [
        ("http://test/v1/auth/google/callback", _extract_state(response.headers["location"]), None)
    ]
    set_cookie = response.headers.get_list("set-cookie")
    assert any("oauth_google_csrf" in header for header in set_cookie)
    assert any("oauth_google_return_to" in header for header in set_cookie)


@pytest.mark.asyncio
async def test_google_callback_creates_user_and_sets_session_cookie(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    client = FakeOAuthClient("google", account_id="acct-new", account_email="new@example.com")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        authorize = await http_client.get("/v1/auth/google/authorize", follow_redirects=False)
        state = _extract_state(authorize.headers["location"])
        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"code": "oauth-code", "state": state},
            follow_redirects=False,
        )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/app"
    assert callback.cookies.get("session") is not None

    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "new@example.com"))).unique().scalar_one()
        oauth_account = (
            await session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
        ).scalar_one()

    assert user.role == "admin"
    assert oauth_account.oauth_name == "google"
    assert oauth_account.account_id == "acct-new"


@pytest.mark.asyncio
async def test_google_callback_auto_links_existing_user_by_email(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    client = FakeOAuthClient("google", account_id="acct-link", account_email="existing@example.com")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with _test_session_factory() as session:
        user = User(
            email="existing@example.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="ro",
        )
        session.add(user)
        await session.commit()
        existing_user_id = user.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        authorize = await http_client.get("/v1/auth/google/authorize", follow_redirects=False)
        state = _extract_state(authorize.headers["location"])
        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"code": "oauth-code", "state": state},
            follow_redirects=False,
        )

    assert callback.status_code == 303
    assert callback.headers["location"] == "/app"
    assert callback.cookies.get("session") is not None

    async with _test_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "existing@example.com"))).unique().scalar_one()
        oauth_account = (
            await session.execute(select(OAuthAccount).where(OAuthAccount.user_id == existing_user_id))
        ).scalar_one()

    assert user.id == existing_user_id
    assert user.role == "ro"
    assert oauth_account.account_id == "acct-link"


@pytest.mark.asyncio
async def test_google_callback_provider_denied_redirects_back_to_browser_login(db_session, monkeypatch):
    _enable_browser_flow(monkeypatch)
    client = FakeOAuthClient("google")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        authorize = await http_client.get(
            "/v1/auth/google/authorize",
            params={"return_to": "https://sandbox-demo.sandbox.localhost/"},
            follow_redirects=False,
        )
        state = _extract_state(authorize.headers["location"])
        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"state": state, "error": "access_denied"},
            follow_redirects=False,
        )

    assert callback.status_code == 303
    assert callback.headers["location"].startswith("/auth/sign-in?")
    assert "return_to=https%3A%2F%2Fsandbox-demo.sandbox.localhost%2F" in callback.headers["location"]


@pytest.mark.asyncio
async def test_google_callback_invalid_state_returns_treadstone_error(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    client = FakeOAuthClient("google")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"code": "oauth-code", "state": "not-a-real-state"},
        )

    assert callback.status_code == 400
    assert callback.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_github_callback_rejects_unverified_email_and_does_not_link_existing_user(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    client = FakeGitHubOAuthClient(
        account_id="gh-unverified",
        account_email="existing@example.com",
        emails=[{"email": "existing@example.com", "primary": True, "verified": False}],
    )
    monkeypatch.setattr(auth_api, "get_github_oauth_client", lambda: client, raising=False)

    async with _test_session_factory() as session:
        user = User(
            email="existing@example.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="ro",
        )
        session.add(user)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        authorize = await http_client.get("/v1/auth/github/authorize", follow_redirects=False)
        state = _extract_state(authorize.headers["location"])
        callback = await http_client.get(
            "/v1/auth/github/callback",
            params={"code": "oauth-code", "state": state},
            follow_redirects=False,
        )

    assert callback.status_code == 400
    assert callback.json()["error"]["code"] == "bad_request"
    assert "verified email" in callback.json()["error"]["message"].lower()

    async with _test_session_factory() as session:
        users = (
            (await session.execute(select(User).where(User.email == "existing@example.com"))).unique().scalars().all()
        )
        oauth_accounts = (await session.execute(select(OAuthAccount))).scalars().all()

    assert len(users) == 1
    assert oauth_accounts == []
