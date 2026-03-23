# Phase 5: Leader Election Implementation Plan

**日期：** 2026-03-24

**Goal:** 为多副本 Treadstone API Server 引入基于 K8s Lease 的 Leader Election，确保任意时刻只有一个副本运行 `Watch + Reconciliation` 后台同步。

**Architecture:** FastAPI `lifespan` 启动 `LeaderControlledSyncSupervisor`。Supervisor 通过 `coordination.k8s.io/v1` Lease 竞争 leadership；只有 leader 才启动 `start_sync_loop()`。非 leader 仅提供 HTTP API。

**Tech Stack:** FastAPI, asyncio, kr8s, Kubernetes Lease API, Helm, pytest

---

### Task 1: 配置与身份注入

**Files:**
- Modify: `treadstone/config.py`
- Modify: `deploy/treadstone/templates/deployment.yaml`
- Modify: `deploy/treadstone/values.yaml`
- Modify: `deploy/treadstone/values-prod.yaml`
- Modify: `deploy/treadstone/values-local.yaml`
- Modify: `deploy/treadstone/values-demo.yaml`

**Step 1: 新增配置字段**

在 `Settings` 中新增：

- `leader_election_enabled: bool = False`
- `leader_election_lease_name: str = "treadstone-sync-leader"`
- `leader_election_lease_duration_seconds: int = 15`
- `leader_election_renew_interval_seconds: int = 5`
- `leader_election_retry_interval_seconds: int = 2`
- `pod_name: str = ""`
- `pod_namespace: str = ""`

**Step 2: 在 Helm deployment 中注入 env**

通过 values + downward API 注入：

- `TREADSTONE_LEADER_ELECTION_ENABLED`
- `TREADSTONE_LEADER_ELECTION_LEASE_NAME`
- `TREADSTONE_LEADER_ELECTION_LEASE_DURATION_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RENEW_INTERVAL_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RETRY_INTERVAL_SECONDS`
- `TREADSTONE_POD_NAME`
- `TREADSTONE_POD_NAMESPACE`

**Step 3: 配置默认值**

- `values.yaml` / `values-local.yaml` / `values-demo.yaml`：`leaderElection.enabled: false`
- `values-prod.yaml`：`leaderElection.enabled: true`

**Step 4: 验证**

运行：

```bash
helm template treadstone-prod deploy/treadstone -f deploy/treadstone/values-prod.yaml
```

确认 env 渲染正确。

---

### Task 2: 实现 Lease 选主服务

**Files:**
- Create: `treadstone/services/leader_election.py`
- Test: `tests/unit/test_leader_election.py`

**Step 1: 先写失败测试**

覆盖至少以下场景：

- Lease 不存在时可以 acquire
- 自己已持有 Lease 时可以 renew
- 他人持有且未过期时返回 follower
- 他人持有但 Lease 已过期时可以抢占
- 更新 Lease 遇到 `409 Conflict` 时不会误判 leader

**Step 2: 实现最小接口**

建议接口：

```python
class LeadershipState(StrEnum):
    LEADER = "leader"
    FOLLOWER = "follower"


class LeaderElector:
    async def try_acquire_or_renew(self) -> LeadershipState: ...
    async def release_if_held(self) -> None: ...
```

实现方式：

- 使用 `kr8s` raw `call_api()` 调用 `Lease` API
- 采用 `GET / POST / PUT` 或 `PATCH` + `resourceVersion` 进行 CAS
- 统一使用 UTC RFC3339 时间

**Step 3: 运行测试**

```bash
uv run pytest tests/unit/test_leader_election.py -v
```

直到全部通过。

---

### Task 3: 接入 Supervisor 与 FastAPI lifespan

**Files:**
- Create: `treadstone/services/sync_supervisor.py`
- Modify: `treadstone/main.py`
- Test: `tests/unit/test_sync_supervisor.py`

**Step 1: 先写失败测试**

覆盖以下行为：

- feature flag 关闭时，supervisor 退化为直接启动 `start_sync_loop`
- 成为 leader 时启动 `start_sync_loop`
- leadership lost 时 cancel sync task
- follower 状态下不会启动 sync task

**Step 2: 实现 supervisor**

建议接口：

```python
class LeaderControlledSyncSupervisor:
    async def run(self) -> None: ...
    async def shutdown(self) -> None: ...
```

职责：

- 循环调用 `LeaderElector.try_acquire_or_renew()`
- `LEADER` 且 sync task 不存在时启动
- `FOLLOWER` 且 sync task 存在时取消
- 应用退出时调用 `release_if_held()`

**Step 3: 修改 `main.py`**

当前直接在 `lifespan()` 中创建 `start_sync_loop()` task。改为：

- `leader_election_enabled = false` 时保持现状
- `leader_election_enabled = true` 时启动 supervisor task

**Step 4: 运行测试**

```bash
uv run pytest tests/unit/test_sync_supervisor.py tests/unit/test_k8s_sync.py -v
```

---

### Task 4: 补充 Lease RBAC

**Files:**
- Modify: `deploy/treadstone/templates/clusterrole.yaml`

**Step 1: 新增 Lease 权限**

追加：

```yaml
- apiGroups:
    - coordination.k8s.io
  resources:
    - leases
  verbs:
    - get
    - list
    - watch
    - create
    - update
    - patch
```

**Step 2: 验证模板**

运行：

```bash
helm template treadstone-prod deploy/treadstone -f deploy/treadstone/values-prod.yaml | rg -n "leases|coordination.k8s.io"
```

---

### Task 5: 回归测试与静态检查

**Files:**
- Modify as needed: `tests/unit/test_k8s_client.py`
- Modify as needed: `tests/unit/test_k8s_sync.py`

**Step 1: 确认旧行为不回归**

至少运行：

```bash
uv run pytest tests/unit/test_k8s_client.py tests/unit/test_k8s_sync.py tests/unit/test_leader_election.py tests/unit/test_sync_supervisor.py -v
```

**Step 2: Lint / Format**

```bash
make format
make lint
```

---

### Task 6: K8s 验证与发布步骤

**Files:**
- No code changes; runbook validation

**Step 1: 渲染 prod chart**

```bash
helm template treadstone-prod deploy/treadstone -f deploy/treadstone/values-prod.yaml
```

确认：

- `leaderElection.enabled` 已开启
- Deployment env 正确
- ClusterRole 包含 Lease 权限

**Step 2: 部署到测试/预发集群**

部署后执行：

```bash
kubectl get lease -n treadstone-prod
kubectl get pods -n treadstone-prod
kubectl logs -n treadstone-prod deploy/treadstone-prod-treadstone --since=10m
```

验证：

- 只有一个 Pod 输出 `leadership acquired`
- 只有 leader 输出 `Watch loop starting`
- follower 不启动 sync loop

**Step 3: 故障切换演练**

```bash
kubectl delete pod -n treadstone-prod <leader-pod-name>
```

确认：

- 另一个副本在一个 Lease TTL 内接管
- 新 leader 启动 `start_sync_loop()`

---

### Task 7: Ship

完成后按 Treadstone 工作流执行：

```bash
git add treadstone/ deploy/treadstone/ tests/
git commit -m "feat: add leader election for multi-replica k8s sync"
```

如需发布到远端分支：

```bash
make ship MSG="feat: add leader election for multi-replica k8s sync"
```

---

## 交付标准

以下条件全部满足才算完成：

- 多副本部署时，只有一个副本运行 `Watch + Reconciliation`
- leader 退出后，其他副本能自动接管
- follower 始终可正常处理 HTTP 请求
- 现有 `k8s_sync` 行为不回归
- Helm chart 渲染出 Lease env + RBAC
- 单元测试、lint、format 全部通过
