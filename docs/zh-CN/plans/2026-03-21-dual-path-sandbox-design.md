# 双路径 Sandbox 供给设计

**日期：** 2026-03-21

**目标：** 实现 SandboxClaim（快速/WarmPool）和直接 Sandbox CR（持久化存储）双路径供给，由 `persist` 参数自动路由。

---

## 1. 背景

### 1.1 agent-sandbox CRD 架构约束

| 资源 | API Group | 支持 volumeClaimTemplates | WarmPool 加速 |
|------|-----------|--------------------------|--------------|
| SandboxClaim | extensions.agents.x-k8s.io | 否（只有 templateRef + lifecycle） | 是 |
| Sandbox | agents.x-k8s.io | 是（spec.volumeClaimTemplates） | 否 |
| SandboxTemplate | extensions.agents.x-k8s.io | 否（只有 podTemplate + networkPolicy） | — |

`SandboxClaim` 无法覆盖模板配置，`volumeClaimTemplates` 仅存在于 `Sandbox` 资源。因此需要持久化存储时必须直接创建 `Sandbox` CR。

### 1.2 解决方案

双路径自动路由：

- **`persist=false`（默认）**：SandboxClaim 路径，引用 SandboxTemplate，享受 WarmPool 预热加速
- **`persist=true`**：直接创建 Sandbox CR，携带 `volumeClaimTemplates`，支持 PVC 持久化

---

## 2. 架构

```
POST /v1/sandboxes { persist: false }          POST /v1/sandboxes { persist: true }
         │                                              │
         ▼                                              ▼
   SandboxService                                 SandboxService
         │                                              │
    persist=false                                  persist=true
         │                                              │
         ▼                                              ▼
  create_sandbox_claim()                     list_sandbox_templates()
  (templateRef → SandboxTemplate)            (查询镜像/资源配额)
         │                                              │
         ▼                                              ▼
  SandboxClaim CR                            create_sandbox()
  (extensions API)                           (core API + volumeClaimTemplates)
         │                                              │
         ▼                                              ▼
  agent-sandbox controller                   Sandbox controller
  可能从 WarmPool 认领 Pod                    创建 Pod + Service + PVCs
         │                                              │
         ▼                                              ▼
  Sandbox CR + Pod + Service                 Sandbox CR + Pod + Service + PVCs
```

**关键事实：** SandboxClaim name == Sandbox name。因此 `start/stop`（`scale_sandbox`）对两种路径统一生效。

---

## 3. 数据模型变更

新增 3 列：

| 列名 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provision_mode` | VARCHAR(16) | `"claim"` | `"claim"` 或 `"direct"`，删除时用于路由 |
| `persist` | BOOLEAN | `false` | 是否有持久化存储 |
| `storage_size` | VARCHAR(32) | NULL | PVC 大小（如 `"10Gi"`），仅 persist=true 时设置 |

保留 `k8s_sandbox_claim_name`（claim 路径使用）。Direct 路径在创建时设置 `k8s_sandbox_name`。

---

## 4. API 变更

### 4.1 创建请求

```json
POST /v1/sandboxes
{
  "template": "aio-sandbox-tiny",
  "name": "my-sandbox",
  "persist": true,
  "storage_size": "20Gi",
  "labels": { "env": "dev" }
}
```

新增字段：
- `persist`（bool，默认 false）
- `storage_size`（string，默认 "10Gi"，仅 persist=true 时生效）

### 4.2 详情响应

新增字段：
- `persist`（bool）
- `storage_size`（string | null）

---

## 5. 服务层路由

### 5.1 创建

```python
if persist:
    # Direct path: lookup template → assemble Sandbox manifest → POST Sandbox CR
    provision_mode = "direct"
    k8s_sandbox_name = sandbox_name
else:
    # Claim path: POST SandboxClaim CR → controller creates Sandbox
    provision_mode = "claim"
    k8s_sandbox_claim_name = sandbox_name
```

### 5.2 删除

```python
if provision_mode == "direct":
    delete_sandbox(k8s_sandbox_name)
elif provision_mode == "claim":
    delete_sandbox_claim(k8s_sandbox_claim_name)
```

### 5.3 启动/停止

不变。`scale_sandbox` 操作 Sandbox CR 的 `replicas` 字段，两种路径都适用。

---

## 6. 不变的部分

- **SandboxTemplate Helm chart**：5 级模板 + WarmPool 保持不变
- **Templates API**：`GET /v1/sandbox-templates` 保持不变
- **K8s 同步**：已通过 `k8s_sandbox_name OR k8s_sandbox_claim_name` 查找，两种路径都兼容
- **Proxy 层**：使用 `k8s_sandbox_name` 路由，不变
- **状态机 / 认证 / Token**：不变

---

## 7. 未来演进

| 方向 | 说明 |
|------|------|
| 自定义存储大小分级 | 预设 small/medium/large 存储选项 |
| 存储快照 | 基于 VolumeSnapshot 的 sandbox 快照/恢复 |
| WarmPool for 持久化 | 如果 agent-sandbox 未来支持 SandboxClaim 携带 volumeClaimTemplates |
