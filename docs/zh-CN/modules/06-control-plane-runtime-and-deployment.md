# 模块 6：控制面运行时、审计与部署

## 模块目标

这个模块描述 Treadstone 控制面如何真正跑起来，包括：

- FastAPI 应用生命周期
- K8s 状态同步
- Leader Election
- 审计与结构化日志
- 本地开发、集群部署与测试入口

## 1. 当前运行时组成

当前服务的启动入口是 `treadstone/main.py`。应用启动时会装配：

- 路由
- 统一错误处理
- CORS
- Sandbox 子域名中间件
- 结构化请求日志中间件
- 后台同步任务

全局错误返回格式固定为：

```json
{"error":{"code":"snake_case_code","message":"...","status":409}}
```

这已经是当前代码的真实约束，不再只是设计目标。

## 2. K8s 状态同步

当前控制面不会把 Sandbox 运行状态长期信任为“写库时的本地状态”，而是通过后台同步去追 K8s 实际状态。

核心组件：

- `treadstone/services/k8s_sync.py`
- `treadstone/services/k8s_client.py`

后台同步做两件事：

- `watch`：实时消费 Sandbox CR 事件
- `reconcile`：周期性全量对账，修正 watch 漏事件和漂移

从 K8s CR 回写 DB 时，当前状态归纳规则是：

- Ready + `replicas=1` -> `ready`
- Ready + `replicas=0` -> `stopped`
- `ReconcilerError` -> `error`
- `SandboxExpired` -> `stopped`
- 依赖未就绪 -> `creating`

## 3. Leader Election

在单进程 / 单副本模式下：

- 应用直接启动 K8s sync loop
- 同时启动 metering tick loop

在多副本模式下：

- 只有 leader 持有者会运行这两个后台循环
- follower 只提供 HTTP API

当前实现使用的是：

- Kubernetes Lease
- `LeaderElector`
- `LeaderControlledSyncSupervisor`

相关配置项包括：

- `TREADSTONE_LEADER_ELECTION_ENABLED`
- `TREADSTONE_LEADER_ELECTION_LEASE_NAME`
- `TREADSTONE_LEADER_ELECTION_LEASE_DURATION_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RENEW_INTERVAL_SECONDS`
- `TREADSTONE_LEADER_ELECTION_RETRY_INTERVAL_SECONDS`
- `TREADSTONE_POD_NAME`
- `TREADSTONE_POD_NAMESPACE`

## 4. 审计与结构化日志

### Audit Event

当前审计模型是 `AuditEvent`，已经覆盖：

- 认证行为
- API Key 管理
- sandbox 创建 / 删除 / Web Link 操作
- 管理员修改套餐与额度
- 系统自动状态迁移

管理员可以通过：

- `GET /v1/audit/events`

按 `action`、`target_type`、`target_id`、`actor_user_id`、`request_id`、`result`、时间范围等条件查询。

### Request Logging

请求日志中间件会输出结构化 JSON，关键字段包括：

- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `client_ip`
- `actor_user_id`
- `actor_api_key_id`
- `credential_type`
- `sandbox_id`
- `route_kind`
- `error_code`

因此，当前仓库的可观测性不是只靠 print 或 access log，而是已经有成体系的请求上下文。

## 5. 部署模型

当前仓库的真实部署模型是：

- **数据库**：Neon Serverless PostgreSQL
- **控制面**：FastAPI + SQLAlchemy async
- **编排层**：Kubernetes + `agent-sandbox`
- **运行时镜像**：`ghcr.io/earayu/treadstone-sandbox`（例如 `v0.2.0`；与 `deploy/sandbox-runtime/values*.yaml` 对齐）
- **本地集群**：Kind

本地开发常用入口：

- `make dev-api`
- `make dev-web`
- `make test`
- `make lint`
- `make migrate`

集群验证入口：

- `make local`（kubectl 指向 Kind；可选 `TREADSTONE_PROD_CONTEXT` 防止误在生产 context 上执行本地操作，见 `deploy/README.md`）
- `make test-e2e`
- `make destroy-local`

## 6. 当前边界

### 已经是当前实现的一部分

- 单进程与多副本两种后台任务运行模型
- K8s watch + reconcile
- 审计事件存储与查询
- 结构化请求日志
- Hurl E2E 测试入口

### 不应再写成当前已存在产品的部分

- 独立前端 Web Console 应用
- Marketplace 业务服务
- 支付与账单系统

这些主题在历史文档里存在，但不再属于当前控制面运行时文档的范围。
