"""API tests for Sandbox Templates endpoint."""

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User
from treadstone.services.k8s_client import FakeK8sClient, set_k8s_client

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
async def auth_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "tmpl@test.com", "password": "Pass123!"})
        async with _test_session_factory() as session:
            user = (await session.execute(select(User).where(User.email == "tmpl@test.com"))).unique().scalar_one()
            user.is_verified = True
            session.add(user)
            await session.commit()
        await client.post("/v1/auth/login", json={"email": "tmpl@test.com", "password": "Pass123!"})
        yield client


async def test_list_templates_is_public(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/sandbox-templates")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 5


async def test_list_templates_returns_items(auth_client):
    resp = await auth_client.get("/v1/sandbox-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 5
    names = [t["name"] for t in data["items"]]
    assert "aio-sandbox-tiny" in names


async def test_template_has_expected_fields(auth_client):
    resp = await auth_client.get("/v1/sandbox-templates")
    tmpl = resp.json()["items"][0]
    assert "name" in tmpl
    assert "display_name" in tmpl
    assert "image" in tmpl
    assert "resource_spec" in tmpl
    assert "runtime_type" not in tmpl


async def test_list_templates_returns_stably_sorted_names(auth_client):
    k8s = FakeK8sClient()
    k8s._templates = [  # noqa: SLF001 - test-only fixture shaping
        {
            "name": "z-template",
            "display_name": "Z",
            "description": "",
            "image": "ghcr.io/earayu/treadstone-sandbox:v0.1.0",
            "resource_spec": {"cpu": "1", "memory": "1Gi"},
            "allowed_storage_sizes": ["5Gi"],
        },
        {
            "name": "a-template",
            "display_name": "A",
            "description": "",
            "image": "ghcr.io/earayu/treadstone-sandbox:v0.1.0",
            "resource_spec": {"cpu": "1", "memory": "1Gi"},
            "allowed_storage_sizes": ["5Gi"],
        },
    ]
    set_k8s_client(k8s)

    resp = await auth_client.get("/v1/sandbox-templates")

    assert resp.status_code == 200
    assert [item["name"] for item in resp.json()["items"]] == ["a-template", "z-template"]


async def test_list_templates_skips_malformed_templates(auth_client):
    k8s = FakeK8sClient()
    k8s._templates = [  # noqa: SLF001 - test-only fixture shaping
        {
            "name": "valid-template",
            "display_name": "Valid",
            "description": "",
            "image": "ghcr.io/earayu/treadstone-sandbox:v0.1.0",
            "resource_spec": {"cpu": "1", "memory": "1Gi"},
            "allowed_storage_sizes": ["5Gi"],
        },
        {
            "name": "broken-template",
            "display_name": "Broken",
            "description": "",
            "image": "ghcr.io/earayu/treadstone-sandbox:v0.1.0",
            "resource_spec": {"cpu": "1"},
            "allowed_storage_sizes": ["5Gi"],
        },
    ]
    set_k8s_client(k8s)

    resp = await auth_client.get("/v1/sandbox-templates")

    assert resp.status_code == 200
    assert [item["name"] for item in resp.json()["items"]] == ["valid-template"]


async def test_list_templates_returns_503_when_catalog_backend_fails(auth_client):
    class FailingK8sClient:
        async def list_sandbox_templates(self, namespace: str) -> list[dict]:
            raise RuntimeError(f"boom:{namespace}")

    set_k8s_client(FailingK8sClient())

    resp = await auth_client.get("/v1/sandbox-templates")

    assert resp.status_code == 503
    data = resp.json()
    assert data["error"]["code"] == "sandbox_template_catalog_unavailable"
