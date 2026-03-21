# Phase 2: Sandbox API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Sandbox API as defined in `docs/zh-CN/plans/2026-03-17-phase2-sandbox-orchestration.md`, including data model, auth migration, control plane CRUD, data plane proxy, Sandbox Token, and K8s state sync.

**Architecture:** FastAPI `/v1/` API with Sandbox model in Neon PG, K8s Watch + Reconciliation for state sync, thin proxy for data plane. Auth migrated from `/api/auth/` to `/v1/auth/` with API Key CRUD. Sandbox Token (JWT) for Agent access.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, httpx, websockets, PyJWT, kr8s or kubernetes-asyncio

---

### Task 1: Sandbox Data Model + Migration

**Files:**
- Create: `treadstone/models/sandbox.py`
- Modify: `treadstone/models/__init__.py`
- Test: `tests/unit/test_sandbox_model.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_sandbox_model.py
from treadstone.models.sandbox import Sandbox, SandboxStatus


def test_sandbox_status_enum():
    assert SandboxStatus.CREATING == "creating"
    assert SandboxStatus.READY == "ready"
    assert SandboxStatus.STOPPED == "stopped"
    assert SandboxStatus.ERROR == "error"
    assert SandboxStatus.DELETING == "deleting"
    assert SandboxStatus.DELETED == "deleted"


def test_sandbox_fields_exist():
    sb = Sandbox()
    for field in [
        "id", "name", "owner_id", "template", "runtime_type", "image",
        "labels", "auto_stop_interval", "auto_delete_interval",
        "k8s_sandbox_name", "k8s_namespace", "k8s_resource_version", "last_synced_at",
        "status", "status_message", "endpoints", "version",
        "gmt_created", "gmt_started", "gmt_stopped", "gmt_deleted",
    ]:
        assert hasattr(sb, field), f"Missing field: {field}"


def test_sandbox_default_values():
    sb = Sandbox()
    assert sb.status == SandboxStatus.CREATING
    assert sb.auto_stop_interval == 15
    assert sb.auto_delete_interval == -1
    assert sb.version == 1
    assert sb.labels == {}
    assert sb.endpoints == {}


def test_sandbox_tablename():
    assert Sandbox.__tablename__ == "sandbox"


VALID_TRANSITIONS: dict[str, list[str]] = {
    "creating": ["ready", "error"],
    "ready": ["stopped", "error", "deleting"],
    "stopped": ["ready", "deleting", "deleted"],
    "error": ["stopped", "deleting"],
    "deleting": ["deleted"],
    "deleted": [],
}


def test_valid_transitions_exist():
    from treadstone.models.sandbox import VALID_TRANSITIONS as transitions
    assert transitions == VALID_TRANSITIONS


def test_is_valid_transition():
    from treadstone.models.sandbox import is_valid_transition
    assert is_valid_transition("creating", "ready") is True
    assert is_valid_transition("creating", "error") is True
    assert is_valid_transition("creating", "deleted") is False
    assert is_valid_transition("deleted", "ready") is False
    assert is_valid_transition("deleting", "ready") is False
    assert is_valid_transition("ready", "deleting") is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_sandbox_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'treadstone.models.sandbox'`

**Step 3: Write minimal implementation**

```python
# treadstone/models/sandbox.py
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class SandboxStatus(StrEnum):
    CREATING = "creating"
    READY = "ready"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"
    DELETED = "deleted"


VALID_TRANSITIONS: dict[str, list[str]] = {
    SandboxStatus.CREATING: [SandboxStatus.READY, SandboxStatus.ERROR],
    SandboxStatus.READY: [SandboxStatus.STOPPED, SandboxStatus.ERROR, SandboxStatus.DELETING],
    SandboxStatus.STOPPED: [SandboxStatus.READY, SandboxStatus.DELETING, SandboxStatus.DELETED],
    SandboxStatus.ERROR: [SandboxStatus.STOPPED, SandboxStatus.DELETING],
    SandboxStatus.DELETING: [SandboxStatus.DELETED],
    SandboxStatus.DELETED: [],
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Sandbox(Base):
    __tablename__ = "sandbox"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "sb" + random_id())
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True
    )

    template: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="aio")
    image: Mapped[str] = mapped_column(String(512), nullable=False)

    labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_stop_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auto_delete_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    k8s_sandbox_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    k8s_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default="treadstone")
    k8s_resource_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SandboxStatus.CREATING)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_stopped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Step 4: Register model in `__init__.py`**

Add to `treadstone/models/__init__.py`:

```python
from treadstone.models.sandbox import Sandbox, SandboxStatus  # noqa: F401
```

Ensure the existing imports are kept.

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_sandbox_model.py -v`
Expected: All PASS

**Step 6: Generate and review migration**

Run: `make migration MSG="add sandbox table"`
Review generated file in `alembic/versions/` — verify table name, columns, FK, indexes.

**Step 7: Lint**

Run: `make format && make lint`
Expected: Clean

**Step 8: Commit**

```bash
git add treadstone/models/sandbox.py treadstone/models/__init__.py tests/unit/test_sandbox_model.py alembic/versions/
git commit -m "feat: add Sandbox data model with state machine and migration"
```

---

### Task 2: Auth Route Migration to `/v1/auth/` + API Key CRUD

**Files:**
- Modify: `treadstone/api/auth.py` (change prefix `/api/auth` → `/v1/auth`, add API Key CRUD endpoints)
- Modify: `treadstone/api/config.py` (change prefix `/api` → `/v1`)
- Modify: `treadstone/main.py` (update `/api/me` → `/v1/me`, OAuth prefix update)
- Modify: `tests/api/test_auth_api.py` (update all URLs from `/api/auth/` → `/v1/auth/`)
- Modify: `tests/api/test_config_api.py` (update URLs)
- Modify: `tests/api/test_health.py` (if references old paths)
- Test: `tests/api/test_api_key_api.py` (new, for API Key CRUD)

**Step 1: Write failing tests for API Key CRUD**

```python
# tests/api/test_api_key_api.py
import pytest


@pytest.fixture
async def auth_client(client):
    """Register + login, return client with auth cookie."""
    await client.post("/v1/auth/register", json={"email": "keyuser@test.com", "password": "Pass123!"})
    await client.post("/v1/auth/login", data={"username": "keyuser@test.com", "password": "Pass123!"})
    return client


async def test_create_api_key(auth_client):
    resp = await auth_client.post("/v1/auth/api-keys", json={"name": "test-key"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-key"
    assert data["key"].startswith("sk-")
    assert "id" in data


async def test_list_api_keys(auth_client):
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-1"})
    await auth_client.post("/v1/auth/api-keys", json={"name": "key-2"})
    resp = await auth_client.get("/v1/auth/api-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 2
    for item in data["items"]:
        assert "key" not in item  # full key not exposed in list
        assert "key_prefix" in item


async def test_delete_api_key(auth_client):
    create_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "to-delete"})
    key_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/v1/auth/api-keys/{key_id}")
    assert resp.status_code == 204
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_api_key_api.py -v`
Expected: FAIL (routes don't exist yet)

**Step 3: Migrate auth router prefix and add API Key CRUD**

In `treadstone/api/auth.py`:
- Change `prefix="/api/auth"` → `prefix="/v1/auth"`
- Add three new endpoints at the bottom: `POST /api-keys`, `GET /api-keys`, `DELETE /api-keys/{key_id}`

In `treadstone/api/config.py`:
- Change `prefix="/api"` → `prefix="/v1"`

In `treadstone/main.py`:
- Change `@app.get("/api/me", ...)` → `@app.get("/v1/me", ...)`
- Change OAuth prefixes from `"/api/auth/google"` → `"/v1/auth/google"`, same for github

**Step 4: Update existing tests to use new paths**

All test files that reference `/api/auth/` must be updated to `/v1/auth/`.
All test files that reference `/api/config` must be updated to `/v1/config`.
All test files that reference `/api/me` must be updated to `/v1/me`.

**Step 5: Run all tests**

Run: `make test`
Expected: All PASS

**Step 6: Lint**

Run: `make format && make lint`

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: migrate auth routes to /v1/ prefix and add API Key CRUD"
```

---

### Task 3: Sandbox CRUD API (Control Plane)

**Files:**
- Create: `treadstone/services/sandbox_service.py`
- Create: `treadstone/api/sandboxes.py` (new router, not the existing `sandbox.py`)
- Modify: `treadstone/main.py` (register new router)
- Test: `tests/unit/test_sandbox_service.py`
- Test: `tests/api/test_sandboxes_api.py`

This task implements the Sandbox lifecycle API:
- `POST /v1/sandboxes` (create, returns 202)
- `GET /v1/sandboxes` (list with label filtering)
- `GET /v1/sandboxes/{id}` (detail)
- `DELETE /v1/sandboxes/{id}` (delete, returns 204)
- `POST /v1/sandboxes/{id}/start`
- `POST /v1/sandboxes/{id}/stop`

K8s integration is **mocked** in this task — the service layer will have a `K8sClient` protocol that is injected, with a stub implementation for testing. Real K8s integration comes in Task 6.

**Step 1: Write failing service tests**

```python
# tests/unit/test_sandbox_service.py
# Test SandboxService.create, get, list_by_owner, delete, start, stop
# Mock the K8sClient and DB session
# Verify state machine transitions, optimistic locking behavior
```

**Step 2: Run tests, verify failure**

Run: `uv run pytest tests/unit/test_sandbox_service.py -v`

**Step 3: Implement SandboxService**

`treadstone/services/sandbox_service.py`:
- `create()`: Write DB record (status=creating), call k8s_client.create_sandbox(), return sandbox
- `get()`: Read from DB only (not K8s)
- `list_by_owner()`: Query DB with optional label filter
- `delete()`: Validate state machine transition, mark deleting, call k8s_client.delete_sandbox()
- `start()`: Validate transition stopped→ready, call k8s
- `stop()`: Validate transition ready→stopped, call k8s

**Step 4: Run service tests, verify pass**

**Step 5: Write failing API tests**

```python
# tests/api/test_sandboxes_api.py
# Test all endpoints with httpx ASGITransport
# K8s client is mocked via dependency override
```

**Step 6: Implement API router**

`treadstone/api/sandboxes.py`:
- Router with `prefix="/v1/sandboxes"`, `tags=["sandboxes"]`
- Pydantic request/response models
- All endpoints delegate to SandboxService

Register in `treadstone/main.py`:
```python
from treadstone.api.sandboxes import router as sandboxes_router
app.include_router(sandboxes_router)
```

**Step 7: Run all tests, verify pass**

Run: `make test`

**Step 8: Lint and commit**

```bash
make format && make lint
git add -A
git commit -m "feat: add Sandbox CRUD API with service layer and state machine"
```

---

### Task 4: Sandbox Proxy Restructure to `/v1/sandboxes/{id}/proxy/`

**Files:**
- Modify: `treadstone/api/sandbox.py` → rename to `treadstone/api/sandbox_proxy.py` (clarity)
- Modify: `treadstone/main.py` (update import)
- Modify: `treadstone/api/sandbox_proxy.py` (new prefix, add auth + ownership check + status check)
- Modify: `tests/api/test_sandbox_api.py` → rename to `tests/api/test_sandbox_proxy_api.py`

The proxy route moves from `/api/sandbox/{sandbox_id}/{path}` to `/v1/sandboxes/{sandbox_id}/proxy/{path}`.
It now requires authentication and checks sandbox ownership + status before proxying.

**Step 1: Write failing tests for new proxy path with auth**

Tests verify:
- `401` without auth
- `404` for non-existent sandbox
- `409` for stopped sandbox
- `200` for valid proxy request (mock httpx response)

**Step 2: Run tests, verify failure**

**Step 3: Implement new proxy router**

- New prefix: `prefix="/v1/sandboxes"`, new route: `/{sandbox_id}/proxy/{path:path}`
- Add `Depends(get_current_user)` or Sandbox Token auth
- Query DB for sandbox record → check ownership → check status is `ready`
- Proxy to `build_sandbox_url()` using existing proxy service

**Step 4: Run all tests, verify pass**

Run: `make test`

**Step 5: Lint and commit**

```bash
make format && make lint
git add -A
git commit -m "feat: restructure sandbox proxy to /v1/sandboxes/{id}/proxy/ with auth"
```

---

### Task 5: Sandbox Token (JWT)

**Files:**
- Create: `treadstone/services/sandbox_token.py`
- Modify: `treadstone/api/sandboxes.py` (add `/token` endpoint)
- Modify: `treadstone/api/deps.py` (add Sandbox Token auth in priority chain)
- Test: `tests/unit/test_sandbox_token.py`
- Test: `tests/api/test_sandbox_token_api.py`

**Step 1: Write failing tests**

Test JWT creation, verification, expiry, and using Sandbox Token to access proxy.

**Step 2: Implement token service**

`treadstone/services/sandbox_token.py`:
- `create_sandbox_token(sandbox_id, user_id, expires_in)` → JWT string
- `verify_sandbox_token(token)` → `{sandbox_id, user_id}` or raise

Uses `PyJWT` (add dependency: `uv add pyjwt`).

**Step 3: Add `/token` endpoint to sandboxes router**

**Step 4: Update `deps.py` auth chain**

Add `authenticate_sandbox_token()` function, update `get_current_user` priority:
```
Sandbox Token > API Key > Cookie
```

Add `get_current_user_or_sandbox_owner()` for proxy endpoint that accepts both user auth and sandbox token.

**Step 5: Run all tests, lint, commit**

```bash
make format && make lint
git add -A
git commit -m "feat: add Sandbox Token (JWT) with auth chain integration"
```

---

### Task 6: Sandbox Templates API (Read-Only from K8s)

**Files:**
- Create: `treadstone/api/sandbox_templates.py`
- Create: `treadstone/services/k8s_client.py`
- Modify: `treadstone/main.py` (register router)
- Test: `tests/unit/test_k8s_client.py`
- Test: `tests/api/test_sandbox_templates_api.py`

**Step 1: Write failing tests**

Mock K8s API to return SandboxTemplate CRs.

**Step 2: Implement K8s client**

`treadstone/services/k8s_client.py`:
- `list_sandbox_templates()` → list of template dicts
- `create_sandbox_cr(name, template, namespace)` → CR dict
- `delete_sandbox_cr(name, namespace)` → bool
- `get_sandbox_cr(name, namespace)` → CR dict or None
- `list_sandbox_crs(namespace)` → list of CR dicts

Uses `kr8s` or `kubernetes-asyncio`. For testing, provide a `FakeK8sClient` implementation.

**Step 3: Implement templates API**

`treadstone/api/sandbox_templates.py`:
- `GET /v1/sandbox-templates` → `{"items": [...]}`

**Step 4: Wire SandboxService to real K8s client**

Update `treadstone/services/sandbox_service.py` to use `K8sClient` protocol instead of stub.

**Step 5: Run all tests, lint, commit**

```bash
make format && make lint
git add -A
git commit -m "feat: add K8s client and sandbox-templates read-only API"
```

---

### Task 7: Unified Error Format

**Files:**
- Create: `treadstone/core/errors.py`
- Modify: `treadstone/main.py` (register exception handlers)
- Modify: `treadstone/api/sandboxes.py` (use new error classes)
- Modify: `treadstone/api/sandbox_proxy.py` (use new error classes)
- Test: `tests/unit/test_errors.py`

**Step 1: Write failing tests**

Test that `TreadstoneError` subclasses produce the correct JSON format:
```json
{"error": {"code": "sandbox_not_found", "message": "...", "status": 404}}
```

**Step 2: Implement error module**

`treadstone/core/errors.py`:
- `TreadstoneError(code, message, status)` base exception
- Subclasses: `SandboxNotFoundError`, `SandboxNotReadyError`, `AuthRequiredError`, etc.

Register a global exception handler in `main.py` that catches `TreadstoneError` and returns the unified JSON format.

**Step 3: Update existing endpoints to raise new errors**

**Step 4: Run all tests, lint, commit**

```bash
make format && make lint
git add -A
git commit -m "feat: add unified error format with structured error codes"
```

---

### Task 8: K8s Watch + Reconciliation (Background Tasks)

**Files:**
- Create: `treadstone/services/k8s_sync.py`
- Modify: `treadstone/main.py` (start Watch + Reconciliation in lifespan)
- Test: `tests/unit/test_k8s_sync.py`

This is the final task, implementing the background state sync from K8s → DB.

**Step 1: Write failing tests**

Test the sync logic (DB updates based on mock K8s events):
- ADDED event → update DB status
- MODIFIED event → validate state transition, update with optimistic lock
- DELETED event → mark deleted if status was deleting, else error
- Reconciliation: List + compare + fix drift

**Step 2: Implement K8s sync service**

`treadstone/services/k8s_sync.py`:
- `start_watch(namespace)` — async generator/loop watching Sandbox CRs
- `handle_watch_event(event_type, cr_object)` — process ADDED/MODIFIED/DELETED
- `reconcile(namespace)` — one-shot List + DB compare
- `start_sync_loop(namespace)` — run Watch + periodic reconciliation

**Step 3: Wire into FastAPI lifespan**

In `main.py` lifespan, start the sync loop as a background `asyncio.Task`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_task = asyncio.create_task(start_sync_loop(settings.sandbox_namespace))
    yield
    sync_task.cancel()
    await close_http_client()
```

**Step 4: Run all tests, lint, commit**

```bash
make format && make lint
git add -A
git commit -m "feat: add K8s Watch + Reconciliation for Sandbox state sync"
```

---

## Execution Order and Dependencies

```
Task 1: Sandbox Model  ──────────────────────────┐
Task 2: Auth Migration + API Key CRUD ────────────┤
                                                   ├─→ Task 3: Sandbox CRUD API
                                                   │     ├─→ Task 4: Proxy Restructure
                                                   │     ├─→ Task 5: Sandbox Token
                                                   │     └─→ Task 7: Unified Errors
                                                   │
                                                   └─→ Task 6: K8s Client + Templates API
                                                           └─→ Task 8: K8s Watch + Reconciliation
```

Tasks 1 and 2 are independent and can be done in parallel.
Tasks 3-8 depend on Tasks 1 and 2 being complete.
Tasks 4, 5, 7 depend on Task 3.
Task 8 depends on Task 6.

## Notes

- Each task should be a **separate PR** targeting `main`, following the development-lifecycle skill.
- Use the database-migration skill for Task 1.
- K8s client is mocked in all tasks except Task 8 (which still needs mocking for unit tests but may have integration tests with Kind).
- All response formats follow the design doc: `{"items": [...], "total": N}` for lists, `{"error": {...}}` for errors.
