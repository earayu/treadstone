"""API tests for API Key CRUD and scope management endpoints."""

from contextlib import contextmanager

import pytest
import sqlalchemy as sa
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.api_key import (
    ApiKey,
    ApiKeyDataPlaneMode,
    ApiKeySandboxGrant,
    build_api_key_preview,
    hash_api_key_secret,
)
from treadstone.models.user import OAuthAccount, User

_test_session_factory = None
_test_engine = None


@contextmanager
def _capture_sql():
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(_test_engine.sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(_test_engine.sync_engine, "before_cursor_execute", before_cursor_execute)


@pytest.fixture
async def db_session():
    global _test_engine, _test_session_factory
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    _test_engine = test_engine
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
    _test_engine = None


@pytest.fixture
async def auth_client(db_session):
    """Register + login, return client with auth cookie."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "keyuser@test.com", "password": "Pass123!"})
        async with _test_session_factory() as session:
            user = (await session.execute(select(User).where(User.email == "keyuser@test.com"))).unique().scalar_one()
            user.is_verified = True
            session.add(user)
            await session.commit()
        await client.post("/v1/auth/login", json={"email": "keyuser@test.com", "password": "Pass123!"})
        yield client


async def test_create_api_key(auth_client):
    resp = await auth_client.post("/v1/auth/api-keys", json={"name": "test-key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["key"].startswith("sk-")
    assert data["scope"] == {
        "control_plane": True,
        "data_plane": {"mode": "all", "sandbox_ids": []},
    }
    assert "id" in data

    async with _test_session_factory() as session:
        api_key = await session.get(ApiKey, data["id"])

    assert api_key is not None
    assert api_key.key_hash == hash_api_key_secret(data["key"])
    assert api_key.key_preview == build_api_key_preview(data["key"])
    assert api_key.key_hash != data["key"]
    assert api_key.control_plane_enabled is True
    assert api_key.data_plane_mode == ApiKeyDataPlaneMode.ALL.value


async def test_create_api_key_with_selected_sandboxes(auth_client):
    first_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "scope-one"})
    second_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "scope-two"})
    first_id = first_resp.json()["id"]
    second_id = second_resp.json()["id"]

    resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={
            "name": "selected-key",
            "scope": {
                "control_plane": False,
                "data_plane": {"mode": "selected", "sandbox_ids": [first_id, second_id]},
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope"] == {
        "control_plane": False,
        "data_plane": {"mode": "selected", "sandbox_ids": [first_id, second_id]},
    }

    async with _test_session_factory() as session:
        api_key = await session.get(ApiKey, data["id"])
        grants = (
            (
                await session.execute(
                    sa.select(ApiKeySandboxGrant.sandbox_id).where(ApiKeySandboxGrant.api_key_id == data["id"])
                )
            )
            .scalars()
            .all()
        )

    assert api_key is not None
    assert api_key.control_plane_enabled is False
    assert api_key.data_plane_mode == ApiKeyDataPlaneMode.SELECTED.value
    assert set(grants) == {first_id, second_id}


async def test_create_api_key_invalid_expiration_returns_422(auth_client):
    resp = await auth_client.post("/v1/auth/api-keys", json={"name": "bad-key", "expires_in": 0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_create_api_key_invalid_scope_returns_422(auth_client):
    resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={
            "name": "bad-scope",
            "scope": {
                "control_plane": True,
                "data_plane": {"mode": "selected", "sandbox_ids": []},
            },
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_list_api_keys(auth_client):
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-1"})
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-2"})
    resp = await auth_client.get("/v1/auth/api-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2
    for item in data["items"]:
        assert "key" not in item
        assert "key_prefix" in item
        assert "scope" in item


async def test_update_api_key_scope_in_place(auth_client):
    first_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "patch-one"})
    second_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "patch-two"})
    first_id = first_resp.json()["id"]
    second_id = second_resp.json()["id"]

    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "patch-key"})
    key_id = create_resp.json()["id"]

    resp = await auth_client.patch(
        f"/v1/auth/api-keys/{key_id}",
        json={
            "name": "patch-key-updated",
            "scope": {
                "control_plane": False,
                "data_plane": {"mode": "selected", "sandbox_ids": [first_id, second_id]},
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "patch-key-updated"
    assert data["scope"] == {
        "control_plane": False,
        "data_plane": {"mode": "selected", "sandbox_ids": [first_id, second_id]},
    }


async def test_data_only_api_key_cannot_access_control_plane(auth_client):
    sandbox_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "control-ban"})
    sandbox_id = sandbox_resp.json()["id"]
    create_resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={
            "name": "data-only",
            "scope": {
                "control_plane": False,
                "data_plane": {"mode": "selected", "sandbox_ids": [sandbox_id]},
            },
        },
    )
    api_key = create_resp.json()["key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/auth/user", headers={"Authorization": f"Bearer {api_key}"})

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_delete_api_key(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "to-delete"})
    key_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/v1/auth/api-keys/{key_id}")
    assert resp.status_code == 204


async def test_create_api_key_is_enabled_by_default(auth_client):
    resp = await auth_client.post("/v1/auth/api-keys", json={"name": "enabled-by-default"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_enabled"] is True


async def test_disable_api_key_blocks_authentication(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "to-disable"})
    assert create_resp.status_code == 201
    key_id = create_resp.json()["id"]
    api_key_value = create_resp.json()["key"]

    # Key works before disabling
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/auth/user", headers={"Authorization": f"Bearer {api_key_value}"})
    assert resp.status_code == 200

    # Disable the key
    patch_resp = await auth_client.patch(f"/v1/auth/api-keys/{key_id}", json={"is_enabled": False})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_enabled"] is False

    # Key no longer works after disabling
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/auth/user", headers={"Authorization": f"Bearer {api_key_value}"})
    assert resp.status_code == 401


async def test_re_enable_api_key_restores_authentication(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "re-enable"})
    key_id = create_resp.json()["id"]
    api_key_value = create_resp.json()["key"]

    await auth_client.patch(f"/v1/auth/api-keys/{key_id}", json={"is_enabled": False})

    # Re-enable
    patch_resp = await auth_client.patch(f"/v1/auth/api-keys/{key_id}", json={"is_enabled": True})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_enabled"] is True

    # Key works again
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/auth/user", headers={"Authorization": f"Bearer {api_key_value}"})
    assert resp.status_code == 200


async def test_list_api_keys_includes_is_enabled(auth_client):
    await auth_client.post("/v1/auth/api-keys", json={"name": "listed-key"})
    resp = await auth_client.get("/v1/auth/api-keys")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert "is_enabled" in item


async def test_api_key_control_plane_auth_loads_user_in_single_select(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "single-select"})
    api_key_value = create_resp.json()["key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with _capture_sql() as statements:
            resp = await client.get("/v1/auth/user", headers={"Authorization": f"Bearer {api_key_value}"})

    assert resp.status_code == 200
    selects = [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1
    assert all("api_key_sandbox_grant" not in statement for statement in selects)
