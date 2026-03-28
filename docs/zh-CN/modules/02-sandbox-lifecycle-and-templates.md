# 模块 2：Sandbox 模板与生命周期

## 模块目标

这个模块定义 Treadstone 控制面的核心对象：`Sandbox`。它负责模板目录、创建方式、生命周期状态和控制面 CRUD。

当前实现主要落在：

- `treadstone/api/sandbox_templates.py`
- `treadstone/api/sandboxes.py`
- `treadstone/models/sandbox.py`
- `treadstone/services/sandbox_service.py`
- `treadstone/services/k8s_client.py`

## 当前模板目录

模板目录是 **Kubernetes 中 SandboxTemplate 的只读投影**，当前对外接口只有：

- `GET /v1/sandbox-templates`

仓库当前内置并测试覆盖的 5 个模板是：

| 模板名 | CPU Request | Memory Request |
| --- | --- | --- |
| `aio-sandbox-tiny` | `250m` | `512Mi` |
| `aio-sandbox-small` | `500m` | `1Gi` |
| `aio-sandbox-medium` | `1` | `2Gi` |
| `aio-sandbox-large` | `2` | `4Gi` |
| `aio-sandbox-xlarge` | `4` | `8Gi` |

这里的模板目录是当前真实的 API 输入源，已经不再是旧文档里的 Marketplace / 模板 CRUD 设计。

## Sandbox 对象

当前 `Sandbox` 表存的是控制面记录，而不是容器运行时的完整镜像快照。关键字段包括：

- `id`
- `name`
- `owner_id`
- `template`
- `runtime_type`
- `labels`
- `auto_stop_interval`
- `auto_delete_interval`
- `persist`
- `storage_size`
- `provision_mode`
- `k8s_sandbox_claim_name`
- `k8s_sandbox_name`
- `k8s_namespace`
- `status`
- `status_message`
- `endpoints`
- `version`

两个非常重要的语义：

- **`id` 是后续操作主键**
- **`name` 只是当前用户范围内的人类可读标签**

当前数据库约束是 `(owner_id, name)` 唯一，而不是全局唯一。

## 创建模式

### 1. 默认模式：`persist=false`

默认走 **claim path**：

- `provision_mode = "claim"`
- 创建 `SandboxClaim`
- 适合短生命周期、无持久卷的 sandbox
- 能利用上游的 WarmPool / 预热能力

### 2. 持久模式：`persist=true`

持久化 sandbox 走 **direct path**：

- `provision_mode = "direct"`
- 直接创建 `Sandbox` CR
- 追加 `volumeClaimTemplates`
- 会先检查 `StorageClass`

当前支持的存储规格只有：

- `5Gi`
- `10Gi`
- `20Gi`

如果 `persist=true` 且未显式传 `storage_size`，会自动回落到 `TREADSTONE_SANDBOX_DEFAULT_STORAGE_SIZE`，默认值是 `5Gi`。

## 生命周期接口

控制面当前公开的 Sandbox 接口是：

- `POST /v1/sandboxes`
- `GET /v1/sandboxes`
- `GET /v1/sandboxes/{sandbox_id}`
- `DELETE /v1/sandboxes/{sandbox_id}`
- `POST /v1/sandboxes/{sandbox_id}/start`
- `POST /v1/sandboxes/{sandbox_id}/stop`

列表接口支持：

- `label=key:value`
- `limit`
- `offset`

## 当前状态机

数据库里真实存在的状态只有 5 个：

- `creating`
- `ready`
- `stopped`
- `error`
- `deleting`

有效迁移规则是：

- `creating -> ready|error|deleting`
- `ready -> stopped|error|deleting`
- `stopped -> ready|deleting`
- `error -> stopped|deleting`

`delete` 并不是同步硬删：

- API 调用阶段先把状态改成 `deleting`
- 等 K8s Watch / Reconcile 观察到底层资源真的消失后，数据库行才会被删除

## 与 Kubernetes 的关系

当前实现遵循两层 source of truth：

- **控制面元数据**：数据库
- **运行状态**：Kubernetes Sandbox CR

也就是说：

- 创建请求先写 DB
- 再去创建 K8s 资源
- 运行状态由后台同步循环回写

持久化 sandbox 在 direct path 下会根据模板 request 推导 limit：

- CPU limit = 2x request
- Memory limit = 2x request

这是当前 `SandboxService` 的真实实现，而不是文档愿景。

## 当前约束

### 1. 名称规则

自定义名称必须：

- 长度 1 到 55
- 只允许小写字母、数字、连字符
- 必须以字母或数字开头和结尾

### 2. 持久卷约束

- `storage_size` 只允许在 `persist=true` 时出现
- `persist=true` 时如果找不到 `StorageClass`，会直接返回 `storage_backend_not_ready`

### 3. 计量接入现状

`SandboxService` 已经预留了计量校验和存储分配记录的接入点，但公开的 `sandboxes` 路由当前仍然是直接实例化 `SandboxService(session=session)`，没有把 `MeteringService` 注入进去。

这意味着当前代码现状是：

- Sandbox 生命周期能力已经稳定存在
- 计量相关的数据模型和 API 已存在
- 但“创建/启动 sandbox 时强制执行套餐限制”这一层还没有在公开路由上完全闭环

