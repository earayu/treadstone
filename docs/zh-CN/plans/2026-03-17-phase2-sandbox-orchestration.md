# Phase 2：Sandbox API 设计文档

**日期：** 2026-03-17（修订 2026-03-19）

**目标：** 定义 Treadstone 平台的核心 Sandbox API，包括控制面（生命周期管理）和数据面（Sandbox 内部功能代理），为 SDK、CLI、Web UI 三种消费者提供统一的 OpenAPI 接口。

---

## 1. 已完成的工作

以下工作在前序 PR 中已完成，本文档在此基础上进行 API 设计。

| 工作项 | 说明 | PR |
|--------|------|----|
| K8s 部署体系 | Helm charts（treadstone / sandbox-runtime / agent-sandbox controller）、Kind 本地集群 | #6, #8 |
| Sandbox Proxy | 自实现 HTTP + WebSocket 反向代理，替代官方 sandbox-router | #11, #12 |
| 子域名路由 | `{sandbox_id}.sandbox.{domain}` 路由到 Sandbox Pod | #11 |
| CD 流水线 | GitHub Actions 构建 Docker 镜像推送 GHCR | #7 |
| 认证系统 | Cookie + API Key + OAuth（Google/GitHub），fastapi-users | #1 |

---

## 2. 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| API 消费者 | 统一 OpenAPI，SDK/CLI/Web 是不同 client | 一套 API 生成多语言 SDK，消费者差异在 client 层面 |
| 数据面抽象 | **薄代理（Thin Proxy）** | Treadstone 只做认证+计费+路由，底层 API 原样透传。不同 Runtime 的 API 差异暴露给调用方 |
| Runtime type | **不体现在 URL 中** | 调用者通过控制面 `GET /v1/sandboxes/{id}` 获取 `runtime_type`，据此决定数据面 API 的使用方式 |
| 版本化 | **URL 前缀 `/v1/`** | 简单直观，SDK 生成友好，Agent 调用不会因漏传 header 出错 |
| Template 管理 | **MVP 预置，只读** | Phase 4 Marketplace 时再开放 CRUD。预置模板通过 Helm chart 部署 |
| 认证 | **API Key/Cookie + Sandbox Token (JWT) 双模式** | API Key 给 CLI/Agent，Cookie 给 Web，Sandbox Token 给 Agent 操作特定 Sandbox |
| 数据面路径 | **Sandbox 资源子路径** `/v1/sandboxes/{id}/proxy/...` | REST 语义清晰，SDK 封装直观 |
| Auth 迁移 | **直接迁移到 `/v1/auth/`** | 开发阶段无需向后兼容 |

---

## 3. URL 全景

```
/v1/
├── auth/                                     # 认证
│   ├── POST   /register                      # 注册
│   ├── POST   /login                         # 登录（返回 JSON token，CLI/Agent 友好）
│   ├── POST   /logout                        # 登出
│   ├── GET    /user                           # 当前用户信息
│   ├── GET    /users                          # 用户列表（admin）
│   ├── POST   /invite                         # 创建邀请（admin）
│   ├── POST   /change-password                # 修改密码
│   ├── DELETE /users/{user_id}                # 删除用户（admin）
│   ├── POST   /api-keys                       # 创建 API Key
│   ├── GET    /api-keys                       # 列出我的 API Key
│   └── DELETE /api-keys/{id}                  # 删除 API Key
│
├── sandbox-templates/                         # 控制面 — 模板（只读）
│   └── GET    /                               # 列出可用模板
│
├── sandboxes/                                 # 控制面 — 生命周期
│   ├── POST   /                               # 创建 Sandbox
│   ├── GET    /                               # 列出我的 Sandbox（?label=k:v）
│   ├── GET    /{id}                           # 查详情
│   ├── DELETE /{id}                           # 删除
│   ├── POST   /{id}/start                     # 启动
│   ├── POST   /{id}/stop                      # 停止
│   ├── POST   /{id}/token                     # 颁发 Sandbox Token
│   │
│   └── ALL    /{id}/proxy/{path:path}         # 数据面 — 透传（HTTP + WS）
│
├── GET  /me                                   # 当前用户（快捷方式）
└── GET  /config                               # 前端配置

/health                                        # 健康检查（无版本前缀）

{sandbox_id}.sandbox.{domain}/                 # 子域名路由（Web UI 浏览器访问）
```

---

## 4. 认证体系

### 4.1 三种认证方式

| 认证方式 | 适用场景 | Header / 机制 |
|----------|----------|---------------|
| **API Key** | CLI、Agent、SDK | `Authorization: Bearer sk-xxx` |
| **Cookie** | Web UI（浏览器） | fastapi-users cookie session |
| **Sandbox Token** | Agent 操作特定 Sandbox | `Authorization: Bearer eyJ...`（JWT） |

### 4.2 认证优先级

```
Sandbox Token (JWT) > API Key (sk-xxx) > Cookie Session
```

Sandbox Token 是 JWT，通过 `POST /v1/sandboxes/{id}/token` 颁发。它的 payload 中包含 `sandbox_id` 和 `user_id`，只能访问对应的 Sandbox。

### 4.3 各端点的认证要求

| 端点类别 | 认证方式 |
|----------|----------|
| `/v1/auth/register`, `/v1/auth/login` | 无需认证 |
| `/v1/auth/*`（其他） | API Key / Cookie |
| `/v1/sandbox-templates` | API Key / Cookie |
| `/v1/sandboxes`（CRUD、start/stop） | API Key / Cookie |
| `/v1/sandboxes/{id}` (GET 详情) | API Key / Cookie / Sandbox Token |
| `/v1/sandboxes/{id}/proxy/*` | API Key / Cookie / Sandbox Token |
| 子域名路由 | Cookie |

### 4.4 CLI / Agent 使用流程

```bash
# 方式 1：交互式登录（人类使用 CLI）
$ treadstone login
Email: user@example.com
Password: ****
✓ Logged in. Token saved to ~/.treadstone/credentials

# 方式 2：配置 API Key（人类或 Agent）
$ treadstone auth set-key sk-xxx
✓ API Key saved

# 方式 3：环境变量（Agent 最友好，零交互）
$ export TREADSTONE_API_KEY=sk-xxx
$ treadstone sandboxes list
```

### 4.5 非交互式登录端点

现有 fastapi-users login 返回 Set-Cookie，对 CLI/Agent 不友好。新增 `/v1/auth/login` 返回 JSON body 中的 token：

```json
POST /v1/auth/login
{ "email": "user@example.com", "password": "xxx" }

→ {
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

## 5. 控制面 API 详细设计

### 5.1 Sandbox Templates（只读）

```
GET /v1/sandbox-templates
```

**响应（200）：**

```json
{
  "items": [
    {
      "name": "python-dev",
      "display_name": "Python Development",
      "description": "Python 3.12 with common data science libraries",
      "runtime_type": "aio",
      "resource_spec": { "cpu": "2", "memory": "2Gi" }
    },
    {
      "name": "nodejs-dev",
      "display_name": "Node.js Development",
      "description": "Node.js 20 with npm/yarn/pnpm",
      "runtime_type": "aio",
      "resource_spec": { "cpu": "2", "memory": "2Gi" }
    }
  ]
}
```

数据来源：K8s 中的 SandboxTemplate CR（通过 Helm chart `deploy/sandbox-runtime/` 部署），Treadstone 通过 K8s API 读取并返回，不存 DB。

### 5.2 创建 Sandbox

```
POST /v1/sandboxes
```

**请求：**

```json
{
  "template": "python-dev",
  "name": "my-sandbox",              // 可选，不填自动生成 sb-{8hex}
  "auto_stop_interval": 15,          // 可选，分钟，0=永不自动停止，默认 15
  "auto_delete_interval": -1,        // 可选，分钟，-1=不自动删除，0=停止后立即删除
  "ephemeral": false,                // 可选，true 等价于 auto_delete_interval=0
  "labels": {                        // 可选，key-value 标签
    "env": "dev",
    "task": "code-review"
  }
}
```

**响应（201）：**

```json
{
  "id": "sb-a1b2c3d4",
  "name": "my-sandbox",
  "template": "python-dev",
  "runtime_type": "aio",
  "status": "creating",
  "labels": { "env": "dev", "task": "code-review" },
  "auto_stop_interval": 15,
  "auto_delete_interval": -1,
  "created_at": "2026-03-19T10:00:00Z"
}
```

### 5.3 列出 Sandbox

```
GET /v1/sandboxes
GET /v1/sandboxes?label=env:dev&label=task:code-review
```

**响应（200）：**

```json
{
  "items": [
    {
      "id": "sb-a1b2c3d4",
      "name": "my-sandbox",
      "template": "python-dev",
      "runtime_type": "aio",
      "status": "ready",
      "labels": { "env": "dev", "task": "code-review" },
      "created_at": "2026-03-19T10:00:00Z"
    }
  ],
  "total": 1
}
```

使用 `{"items": [...], "total": N}` 格式而非裸数组，方便未来加分页。

### 5.4 查询 Sandbox 详情

```
GET /v1/sandboxes/{id}
```

**响应（200）：**

```json
{
  "id": "sb-a1b2c3d4",
  "name": "my-sandbox",
  "template": "python-dev",
  "runtime_type": "aio",
  "status": "ready",
  "labels": { "env": "dev", "task": "code-review" },
  "auto_stop_interval": 15,
  "auto_delete_interval": -1,
  "proxy_url": "/v1/sandboxes/sb-a1b2c3d4/proxy",
  "created_at": "2026-03-19T10:00:00Z",
  "started_at": "2026-03-19T10:00:30Z"
}
```

### 5.5 删除 Sandbox

```
DELETE /v1/sandboxes/{id}
```

**响应（204）：** 无 body。重复调用返回 204（幂等）。

### 5.6 启动 / 停止

```
POST /v1/sandboxes/{id}/start
POST /v1/sandboxes/{id}/stop
```

**响应（200）：** 返回更新后的 Sandbox 详情。

### 5.7 颁发 Sandbox Token

```
POST /v1/sandboxes/{id}/token
```

**请求：**

```json
{
  "expires_in": 3600    // 可选，秒，默认跟随 sandbox 剩余 auto_stop 时间
}
```

**响应（201）：**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "sandbox_id": "sb-a1b2c3d4",
  "expires_at": "2026-03-19T11:00:00Z"
}
```

JWT payload 包含 `sandbox_id`、`user_id`、`exp`。持有此 token 只能访问对应 Sandbox 的详情和 proxy。

### 5.8 Sandbox 状态机

```
creating → ready → stopped → deleting → deleted
              ↕        ↑
           running     │
              ↓        │
            error ─────┘
```

| 状态 | 说明 |
|------|------|
| `creating` | Sandbox Pod 正在创建 |
| `ready` | Pod 就绪，可以接收请求（等价于 running） |
| `running` | 正在被使用（有活跃连接） |
| `stopped` | 已停止，可通过 `start` 恢复 |
| `error` | 出错，可尝试 `stop` 后重新 `start` |
| `deleting` | 正在删除 |
| `deleted` | 已删除（终态） |

MVP 阶段不实现 `archived` 状态（需要对象存储支持），可在 Phase 5 引入。

---

## 6. 数据面 API（Proxy）详细设计

### 6.1 路由

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| ALL | `/v1/sandboxes/{id}/proxy/{path:path}` | HTTP 透传到 Sandbox Pod | API Key / Cookie / Sandbox Token |
| WS | `/v1/sandboxes/{id}/proxy/{path:path}` | WebSocket 透传 | API Key / Cookie / Sandbox Token |

### 6.2 工作原理

```
Agent/SDK                          Treadstone                         Sandbox Pod
   │                                   │                                   │
   │  POST /v1/sandboxes/sb-123/       │                                   │
   │       proxy/v1/shell/exec         │                                   │
   │  Header: Authorization: Bearer xx │                                   │
   │  Body: {"command": "ls -la"}      │                                   │
   │──────────────────────────────────→│                                   │
   │                                   │  1. 验证 token                    │
   │                                   │  2. 校验 sandbox 归属权           │
   │                                   │  3. 校验 sandbox 状态             │
   │                                   │  4. 记录计费事件                  │
   │                                   │  5. 解析目标 Pod 地址             │
   │                                   │                                   │
   │                                   │  POST sb-123.ns.svc:8080/         │
   │                                   │       v1/shell/exec               │
   │                                   │  Body: {"command": "ls -la"}      │
   │                                   │──────────────────────────────────→│
   │                                   │                                   │
   │                                   │←──────────────────────────────────│
   │←──────────────────────────────────│                                   │
   │  200 {"data": {"output": "..."}}  │                                   │
```

### 6.3 Treadstone Proxy 层职责

**做：**

| 职责 | 说明 |
|------|------|
| 认证 | 验证 API Key / Cookie / Sandbox Token |
| 权限校验 | 确认该用户/token 有权访问此 Sandbox |
| 状态校验 | Sandbox 必须处于 `ready` / `running` 状态 |
| 计费记录 | 记录请求事件（MVP 先记日志，Phase 3 接入计费） |
| 路由解析 | 根据 `sandbox_id` 找到目标 Pod 地址 |
| 透传 | 请求原样转发，响应原样返回 |

**不做：**

- 不解析/转换底层 API 的请求和响应格式
- 不校验 `{path}` 是否合法（底层 Runtime 自己处理 404）
- 不限制可调用的底层 API（安全限制在 Runtime 侧做）

### 6.4 以 AIO Sandbox 为例的调用路径

调用者通过 `GET /v1/sandboxes/{id}` 获取 `runtime_type: "aio"`，然后按 AIO 的 API 文档拼 path：

| 能力 | 完整调用路径 |
|------|-------------|
| 执行命令 | `POST /v1/sandboxes/{id}/proxy/v1/shell/exec` |
| 读文件 | `POST /v1/sandboxes/{id}/proxy/v1/file/read` |
| 写文件 | `POST /v1/sandboxes/{id}/proxy/v1/file/write` |
| 搜索文件内容 | `POST /v1/sandboxes/{id}/proxy/v1/file/search` |
| 查找文件 | `POST /v1/sandboxes/{id}/proxy/v1/file/find` |
| 替换文件内容 | `POST /v1/sandboxes/{id}/proxy/v1/file/replace` |
| 浏览器截图 | `GET  /v1/sandboxes/{id}/proxy/v1/browser/screenshot` |
| 浏览器操作 | `POST /v1/sandboxes/{id}/proxy/v1/browser/actions` |
| Jupyter 执行 | `POST /v1/sandboxes/{id}/proxy/v1/jupyter/execute` |
| Sandbox 上下文 | `GET  /v1/sandboxes/{id}/proxy/v1/sandbox` |
| Shell WebSocket | `WS   /v1/sandboxes/{id}/proxy/v1/shell/ws` |
| VNC 桌面 | `WS   /v1/sandboxes/{id}/proxy/vnc/index.html` |
| MCP Hub | `POST /v1/sandboxes/{id}/proxy/mcp` |
| Web UI Dashboard | `GET  /v1/sandboxes/{id}/proxy/index.html` |

### 6.5 子域名访问（Web UI 场景）

与 path-based proxy 并行，保留子域名路由给浏览器访问：

```
{sandbox_id}.sandbox.treadstone.dev  →  Sandbox Pod:8080
```

| 场景 | 路由 | 原因 |
|------|------|------|
| 人在浏览器里用 Sandbox | 子域名 | 浏览器体验自然，相对路径和 WS 自动 work |
| Agent/SDK 调 API | path-based proxy | 程序化调用，URL 可预测，不依赖 DNS |

两条路径都支持 HTTP 和 WebSocket，按消费者分，不按协议分。

---

## 7. API Key 管理

### 7.1 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/auth/api-keys` | 创建 API Key |
| GET | `/v1/auth/api-keys` | 列出我的 API Key |
| DELETE | `/v1/auth/api-keys/{id}` | 删除 API Key |

### 7.2 创建 API Key

```
POST /v1/auth/api-keys
```

**请求：**

```json
{
  "name": "my-agent-key"    // 可选，便于识别
}
```

**响应（201）：**

```json
{
  "id": "key-abc123",
  "name": "my-agent-key",
  "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "created_at": "2026-03-19T10:00:00Z"
}
```

`key` 字段只在创建时返回一次，后续查询只返回前缀 `sk-xxxx...xxxx`。

### 7.3 列出 API Key

```
GET /v1/auth/api-keys
```

**响应（200）：**

```json
{
  "items": [
    {
      "id": "key-abc123",
      "name": "my-agent-key",
      "key_prefix": "sk-xxxx...xxxx",
      "created_at": "2026-03-19T10:00:00Z"
    }
  ]
}
```

---

## 8. 统一错误格式

所有 Treadstone 自身产生的错误（非 proxy 透传的底层 Runtime 错误）使用统一格式：

```json
{
  "error": {
    "code": "sandbox_not_found",
    "message": "Sandbox sb-xyz does not exist or you don't have access to it.",
    "status": 404
  }
}
```

| 字段 | 说明 |
|------|------|
| `code` | 机器可读错误码，SDK 可用于 switch/match |
| `message` | 人类可读描述 |
| `status` | HTTP 状态码（冗余但方便 SDK） |

### 错误码表

| code | status | 场景 |
|------|--------|------|
| `auth_required` | 401 | 未提供认证凭据 |
| `auth_invalid` | 401 | 凭据无效或过期 |
| `forbidden` | 403 | 无权访问此资源 |
| `sandbox_not_found` | 404 | Sandbox 不存在 |
| `template_not_found` | 404 | Template 不存在 |
| `sandbox_not_ready` | 409 | Sandbox 状态不允许此操作（如 stopped、creating） |
| `sandbox_unreachable` | 502 | 无法连接到 Sandbox Pod |
| `sandbox_timeout` | 504 | Sandbox Pod 响应超时 |
| `validation_error` | 422 | 请求参数校验失败 |

Proxy 透传时，底层 Runtime 返回的错误码原样返回（如 AIO 的 400、404、500 等），不包装为上述格式。

---

## 9. SDK 友好性设计

| 要点 | 说明 |
|------|------|
| **OpenAPI operationId** | 使用 `custom_generate_unique_id`（tag + 函数名），生成的 SDK 方法名可读 |
| **列表响应统一格式** | `{"items": [...], "total": N}` 而非裸数组，方便未来加分页 |
| **action 用 POST** | `start`、`stop`、`token` 是动作不是更新，POST 语义更清晰 |
| **id 格式** | `sb-` 前缀 + 8 字符 hex，短且可辨识，CLI 中方便 copy-paste |
| **幂等性** | DELETE 重复调用返回 204，POST create 可用 `name` 做幂等键 |
| **环境变量优先** | SDK/CLI 按 `TREADSTONE_API_KEY` → config file → interactive login 顺序解析认证 |

---

## 10. 架构总览

```
用户 / Agent / CLI / Web UI
         │
         │  TREADSTONE_API_KEY=sk-xxx
         │  或 Sandbox Token (JWT)
         │  或 Cookie
         ▼
┌──────────────────────────────────────────────────┐
│  Treadstone API (FastAPI)                         │
│                                                   │
│  /v1/auth/*          认证、API Key 管理           │
│  /v1/sandbox-templates  模板查询（K8s CR 只读）    │
│  /v1/sandboxes/*     生命周期 CRUD + start/stop   │
│  /v1/sandboxes/{id}/proxy/*  数据面透传           │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Proxy 层                                    │  │
│  │  认证 → 权限校验 → 状态校验 → 计费 → 转发    │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────┬────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌────────┐ ┌────────────┐ ┌──────────┐
│ Neon   │ │ K8s API    │ │ Sandbox  │
│ (PG)   │ │ (CRD)     │ │ Pods     │
│        │ │            │ │          │
│ User   │ │ Sandbox CR │ │ AIO:8080 │
│ ApiKey │ │ Template   │ │ Other:?  │
│ Sandbox│ │ WarmPool   │ │          │
└────────┘ └────────────┘ └──────────┘
```

---

## 11. 与其他 Phase 的关系

| Phase | 与本设计的关系 |
|-------|---------------|
| **Phase 1（已完成）** | Auth 路由从 `/api/auth/` 迁移到 `/v1/auth/`，补充 API Key CRUD 和 JSON login |
| **Phase 3（计费）** | Proxy 层的"计费记录"从日志升级为真实计费事件 |
| **Phase 4（Marketplace）** | `sandbox-templates` 从只读升级为 CRUD，加入描述、作者、定价等元数据 |
| **Phase 5（生产化）** | 可引入 `archived` 状态、分页、限流、Sandbox resize 等 |

---

## 12. 参考

- [Daytona Sandboxes 文档](https://www.daytona.io/docs/en/sandboxes/) — Sandbox 生命周期、SDK 设计、auto-stop/auto-archive/auto-delete
- [AIO Sandbox (agent-infra/sandbox)](https://github.com/agent-infra/sandbox) — 内部 API（`/v1/shell/*`, `/v1/file/*`, `/v1/browser/*` 等）
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) — CRD 编排层
