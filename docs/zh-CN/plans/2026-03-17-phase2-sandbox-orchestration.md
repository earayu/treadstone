# Phase 2：核心沙箱编排 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 K8s 上通过 kubernetes-sigs/agent-sandbox CRD 创建和管理沙箱，Pod 内运行 agent-infra/sandbox 镜像，暴露 REST API 供用户/Agent 操作沙箱。

**Architecture:** FastAPI → k8s_client.py (agent-sandbox Python SDK) → K8s API → agent-sandbox controller → Pod (agent-infra/sandbox)。沙箱元数据存 PostgreSQL，运行状态从 K8s CR 实时查询。

**Tech Stack:** kubernetes-sigs/agent-sandbox v0.2.x (Python SDK), agent-infra/sandbox Docker image, Kind + gVisor (开发环境), FastAPI

---

### Task 1：搭建开发 K8s 环境

**Files:**
- Create: `scripts/setup-dev-cluster.sh`

**Step 1: 写集群搭建脚本**

```bash
#!/bin/bash
set -euo pipefail

# 创建 Kind 集群（支持 gVisor 需要额外配置，开发阶段先用普通容器）
kind create cluster --name treadstone-dev --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
EOF

# 安装 agent-sandbox controller
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/agent-sandbox.yaml

# 等待 controller 就绪
kubectl wait --for=condition=available --timeout=120s deployment/agent-sandbox-controller-manager -n agent-sandbox-system

echo "✓ Dev cluster ready"
```

**Step 2: 运行脚本**

```bash
chmod +x scripts/setup-dev-cluster.sh
./scripts/setup-dev-cluster.sh
```

Expected: Kind 集群创建成功，agent-sandbox controller running

**Step 3: 验证 CRD 已安装**

```bash
kubectl get crd | grep sandbox
```

Expected: 看到 sandboxes.agent-sandbox.sigs.k8s.io 等 CRD

**Step 4: Commit**

```bash
git add scripts/setup-dev-cluster.sh
git commit -m "chore: dev k8s cluster setup script with agent-sandbox"
```

---

### Task 2：手动验证 agent-infra/sandbox 在 K8s 中运行

**Files:**
- Create: `deploy/sandbox-test.yaml`

**Step 1: 写测试用 Sandbox CR**

```yaml
# deploy/sandbox-test.yaml
apiVersion: agent-sandbox.sigs.k8s.io/v1alpha1
kind: Sandbox
metadata:
  name: test-sandbox
spec:
  template:
    spec:
      containers:
        - name: sandbox
          image: ghcr.io/agent-infra/sandbox:latest
          ports:
            - containerPort: 8080
          securityContext:
            seccompProfile:
              type: Unconfined
```

**Step 2: 部署并验证**

```bash
kubectl apply -f deploy/sandbox-test.yaml
kubectl wait --for=condition=ready sandbox/test-sandbox --timeout=120s
kubectl port-forward sandbox/test-sandbox 8080:8080
```

访问 http://localhost:8080/v1/docs 验证 agent-infra/sandbox API 可用

**Step 3: 清理**

```bash
kubectl delete -f deploy/sandbox-test.yaml
```

**Step 4: Commit**

```bash
git add deploy/sandbox-test.yaml
git commit -m "chore: test sandbox CR with agent-infra/sandbox image"
```

---

### Task 3：k8s_client.py 适配层

**Files:**
- Create: `treadstone/core/k8s_client.py`
- Test: `tests/test_k8s_client.py`

**Step 1: 添加依赖**

```bash
uv add agent-sandbox
```

（如果 agent-sandbox SDK 不在 PyPI，则 `uv add git+https://github.com/kubernetes-sigs/agent-sandbox.git#subdirectory=sdk/python`）

**Step 2: 写测试（mock K8s API）**

```python
# tests/test_k8s_client.py
import pytest
from unittest.mock import AsyncMock, patch

from treadstone.core.k8s_client import SandboxK8sClient


@pytest.mark.asyncio
async def test_create_sandbox():
    client = SandboxK8sClient()
    with patch.object(client, "_sdk_client") as mock_sdk:
        mock_sdk.create_sandbox = AsyncMock(return_value={"name": "sb-123", "status": "creating"})
        result = await client.create_sandbox(
            name="sb-123",
            image="ghcr.io/agent-infra/sandbox:latest",
            template="python-dev",
        )
    assert result["name"] == "sb-123"


@pytest.mark.asyncio
async def test_get_sandbox_status():
    client = SandboxK8sClient()
    with patch.object(client, "_sdk_client") as mock_sdk:
        mock_sdk.get_sandbox = AsyncMock(return_value={"name": "sb-123", "status": "ready", "endpoint": "http://10.0.0.1:8080"})
        result = await client.get_sandbox("sb-123")
    assert result["status"] == "ready"


@pytest.mark.asyncio
async def test_delete_sandbox():
    client = SandboxK8sClient()
    with patch.object(client, "_sdk_client") as mock_sdk:
        mock_sdk.delete_sandbox = AsyncMock(return_value=True)
        result = await client.delete_sandbox("sb-123")
    assert result is True
```

**Step 3: 运行测试确认失败**

```bash
uv run pytest tests/test_k8s_client.py -v
```

**Step 4: 实现 k8s_client.py**

```python
# treadstone/core/k8s_client.py
from dataclasses import dataclass


@dataclass
class SandboxInfo:
    name: str
    status: str
    endpoint: str | None = None
    created_at: str | None = None


class SandboxK8sClient:
    """封装 kubernetes-sigs/agent-sandbox Python SDK。
    所有 K8s 交互通过此类进行，未来换编排层只改此文件。
    """

    def __init__(self):
        # 初始化 agent-sandbox SDK client
        # 具体初始化方式取决于 SDK 版本，需参考最新文档
        self._sdk_client = None  # placeholder，实际集成时替换

    async def create_sandbox(self, name: str, image: str, template: str | None = None) -> dict:
        """创建沙箱，返回沙箱信息。"""
        # 通过 SDK 创建 SandboxClaim 或直接创建 Sandbox CR
        # 返回 {"name": ..., "status": "creating"}
        raise NotImplementedError("需要集成 agent-sandbox SDK")

    async def get_sandbox(self, name: str) -> dict:
        """查询沙箱状态和端点。"""
        raise NotImplementedError("需要集成 agent-sandbox SDK")

    async def list_sandboxes(self, owner_id: str | None = None) -> list[dict]:
        """列出沙箱。"""
        raise NotImplementedError("需要集成 agent-sandbox SDK")

    async def delete_sandbox(self, name: str) -> bool:
        """删除沙箱。"""
        raise NotImplementedError("需要集成 agent-sandbox SDK")
```

注意：此处是接口骨架。实际集成 agent-sandbox SDK 的代码需要参考 SDK 最新文档。SDK 的 API 可能是同步的（基于 kubernetes python client），需要用 `asyncio.to_thread` 包装为 async。

**Step 5: Commit**

```bash
git add treadstone/core/k8s_client.py tests/test_k8s_client.py
git commit -m "feat: k8s client adapter for agent-sandbox SDK"
```

---

### Task 4：Sandbox 数据模型

**Files:**
- Create: `treadstone/models/sandbox.py`
- Test: `tests/test_sandbox_model.py`

**Step 1: 写测试**

验证 Sandbox model 的字段、状态枚举。

**Step 2: 实现 Sandbox model**

```python
# treadstone/models/sandbox.py
import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base


class SandboxStatus(str, enum.Enum):
    CREATING = "creating"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    DELETING = "deleting"


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    template: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[SandboxStatus] = mapped_column(Enum(SandboxStatus), default=SandboxStatus.CREATING)
    k8s_sandbox_name: Mapped[str] = mapped_column(String(255), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Step 3: 生成迁移**

```bash
uv run alembic revision --autogenerate -m "add sandboxes table"
uv run alembic upgrade head
```

**Step 4: Commit**

```bash
git add treadstone/models/sandbox.py alembic/versions/ tests/
git commit -m "feat: sandbox data model with status enum"
```

---

### Task 5：沙箱 CRUD Service

**Files:**
- Create: `treadstone/services/sandbox_service.py`
- Test: `tests/test_sandbox_service.py`

**Step 1: 写测试**

- `test_create_sandbox`：创建沙箱 → DB 记录 + K8s 调用
- `test_get_sandbox`：查询沙箱 → 从 DB 获取 + 从 K8s 同步状态
- `test_delete_sandbox`：删除沙箱 → K8s 删除 + DB 标记删除
- `test_list_user_sandboxes`：列出用户的沙箱

（mock K8sClient）

**Step 2: 实现 sandbox_service.py**

```python
# treadstone/services/sandbox_service.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.core.k8s_client import SandboxK8sClient
from treadstone.models.sandbox import Sandbox, SandboxStatus


class SandboxService:
    def __init__(self, session: AsyncSession, k8s_client: SandboxK8sClient):
        self.session = session
        self.k8s = k8s_client

    async def create(self, owner_id: uuid.UUID, template: str) -> Sandbox:
        sandbox = Sandbox(
            name=f"sb-{uuid.uuid4().hex[:8]}",
            owner_id=owner_id,
            template=template,
            status=SandboxStatus.CREATING,
        )
        self.session.add(sandbox)
        await self.session.flush()

        k8s_result = await self.k8s.create_sandbox(
            name=sandbox.name,
            image="ghcr.io/agent-infra/sandbox:latest",
            template=template,
        )
        sandbox.k8s_sandbox_name = k8s_result["name"]
        await self.session.commit()
        return sandbox

    async def get(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        sandbox = await self.session.get(Sandbox, sandbox_id)
        if sandbox and sandbox.status not in (SandboxStatus.STOPPED, SandboxStatus.FAILED):
            k8s_info = await self.k8s.get_sandbox(sandbox.name)
            sandbox.status = SandboxStatus(k8s_info["status"])
            sandbox.endpoint = k8s_info.get("endpoint")
            await self.session.commit()
        return sandbox

    async def list_by_owner(self, owner_id: uuid.UUID) -> list[Sandbox]:
        result = await self.session.execute(
            select(Sandbox).where(Sandbox.owner_id == owner_id, Sandbox.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def delete(self, sandbox_id: uuid.UUID) -> bool:
        sandbox = await self.session.get(Sandbox, sandbox_id)
        if not sandbox:
            return False
        await self.k8s.delete_sandbox(sandbox.name)
        sandbox.status = SandboxStatus.DELETING
        await self.session.commit()
        return True
```

**Step 3: Commit**

```bash
git add treadstone/services/sandbox_service.py tests/test_sandbox_service.py
git commit -m "feat: sandbox CRUD service with k8s integration"
```

---

### Task 6：沙箱 API 路由

**Files:**
- Create: `treadstone/api/sandbox.py`
- Modify: `treadstone/main.py`（注册 router）
- Test: `tests/test_sandbox_api.py`

**Step 1: 写测试**

- `test_create_sandbox_api`：POST /api/sandboxes → 201
- `test_get_sandbox_api`：GET /api/sandboxes/{id} → 200
- `test_list_sandboxes_api`：GET /api/sandboxes → 200 + list
- `test_delete_sandbox_api`：DELETE /api/sandboxes/{id} → 204
- `test_create_sandbox_unauthorized`：无 token → 401

**Step 2: 实现 sandbox.py router**

```python
# treadstone/api/sandbox.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_user
from treadstone.core.database import get_session
from treadstone.core.k8s_client import SandboxK8sClient
from treadstone.models.user import User
from treadstone.services.sandbox_service import SandboxService

router = APIRouter(prefix="/api/sandboxes", tags=["sandboxes"])


class CreateSandboxRequest(BaseModel):
    template: str


class SandboxResponse(BaseModel):
    id: uuid.UUID
    name: str
    template: str
    status: str
    endpoint: str | None
    created_at: str

    model_config = {"from_attributes": True}


def get_sandbox_service(session: AsyncSession = Depends(get_session)) -> SandboxService:
    return SandboxService(session=session, k8s_client=SandboxK8sClient())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SandboxResponse)
async def create_sandbox(
    req: CreateSandboxRequest,
    user: User = Depends(get_current_user),
    svc: SandboxService = Depends(get_sandbox_service),
):
    sandbox = await svc.create(owner_id=user.id, template=req.template)
    return sandbox


@router.get("", response_model=list[SandboxResponse])
async def list_sandboxes(
    user: User = Depends(get_current_user),
    svc: SandboxService = Depends(get_sandbox_service),
):
    return await svc.list_by_owner(owner_id=user.id)


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: SandboxService = Depends(get_sandbox_service),
):
    sandbox = await svc.get(sandbox_id)
    if not sandbox or sandbox.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return sandbox


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    sandbox_id: uuid.UUID,
    user: User = Depends(get_current_user),
    svc: SandboxService = Depends(get_sandbox_service),
):
    sandbox = await svc.get(sandbox_id)
    if not sandbox or sandbox.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    await svc.delete(sandbox_id)
```

**Step 3: 在 main.py 注册 router**

```python
from treadstone.api.sandbox import router as sandbox_router
app.include_router(sandbox_router)
```

**Step 4: Commit**

```bash
git add treadstone/api/sandbox.py treadstone/main.py tests/test_sandbox_api.py
git commit -m "feat: sandbox CRUD API endpoints"
```

---

### Task 7：SandboxTemplate 预置模板

**Files:**
- Create: `deploy/templates/python-dev.yaml`
- Create: `deploy/templates/nodejs-dev.yaml`
- Create: `deploy/templates/linux-general.yaml`
- Create: `scripts/apply-templates.sh`

**Step 1: 写预置 SandboxTemplate CRD**

```yaml
# deploy/templates/python-dev.yaml
apiVersion: agent-sandbox.sigs.k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: python-dev
  labels:
    treadstone.io/category: development
spec:
  template:
    spec:
      containers:
        - name: sandbox
          image: ghcr.io/agent-infra/sandbox:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
          securityContext:
            seccompProfile:
              type: Unconfined
```

（nodejs-dev 和 linux-general 结构类似，资源配额不同）

**Step 2: 写应用脚本**

```bash
#!/bin/bash
# scripts/apply-templates.sh
set -euo pipefail
kubectl apply -f deploy/templates/
echo "✓ Sandbox templates applied"
kubectl get sandboxtemplates
```

**Step 3: Commit**

```bash
git add deploy/templates/ scripts/apply-templates.sh
git commit -m "feat: preset sandbox templates (python/nodejs/linux)"
```

---

### Task 8：WarmPool 配置

**Files:**
- Create: `deploy/warmpool.yaml`

**Step 1: 写 WarmPool CRD**

```yaml
# deploy/warmpool.yaml
apiVersion: agent-sandbox.sigs.k8s.io/v1alpha1
kind: SandboxWarmPool
metadata:
  name: default-warmpool
spec:
  templateRef:
    name: python-dev
  replicas: 2
```

**Step 2: 部署并验证**

```bash
kubectl apply -f deploy/warmpool.yaml
kubectl get sandboxes
```

Expected: 看到 2 个预热的 sandbox Pod

**Step 3: Commit**

```bash
git add deploy/warmpool.yaml
git commit -m "feat: warm pool for fast sandbox allocation"
```

---

### Task 9：端到端集成测试

**Files:**
- Create: `tests/integration/test_sandbox_e2e.py`

**Step 1: 写端到端测试**

前提：需要一个运行中的 K8s 集群（CI 中用 Kind）。

```python
# tests/integration/test_sandbox_e2e.py
"""
端到端测试：通过 API 创建沙箱 → 等待就绪 → 访问沙箱端点 → 删除沙箱。
需要运行中的 K8s 集群，CI 中通过 Kind 提供。
本地运行：先执行 scripts/setup-dev-cluster.sh
"""
import asyncio
import pytest
import httpx


API_BASE = "http://localhost:8000"


@pytest.mark.integration
class TestSandboxE2E:
    async def test_full_lifecycle(self):
        async with httpx.AsyncClient(base_url=API_BASE) as client:
            # 注册
            await client.post("/api/auth/register", json={"email": "e2e@test.com", "password": "testpass123"})
            # 登录
            resp = await client.post("/api/auth/login", json={"email": "e2e@test.com", "password": "testpass123"})
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 创建沙箱
            resp = await client.post("/api/sandboxes", json={"template": "python-dev"}, headers=headers)
            assert resp.status_code == 201
            sandbox_id = resp.json()["id"]

            # 轮询等待就绪（最多 60 秒）
            for _ in range(30):
                resp = await client.get(f"/api/sandboxes/{sandbox_id}", headers=headers)
                if resp.json()["status"] == "ready":
                    break
                await asyncio.sleep(2)

            assert resp.json()["status"] == "ready"
            assert resp.json()["endpoint"] is not None

            # 删除沙箱
            resp = await client.delete(f"/api/sandboxes/{sandbox_id}", headers=headers)
            assert resp.status_code == 204
```

**Step 2: Commit**

```bash
git add tests/integration/
git commit -m "test: sandbox end-to-end integration test"
```
