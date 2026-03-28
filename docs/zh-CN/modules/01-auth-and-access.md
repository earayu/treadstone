# 模块 1：认证与访问控制

## 模块目标

这个模块负责回答三个问题：

- 用户是谁
- 当前请求拿的是什么凭证
- 这个凭证能访问控制面还是数据面

当前实现的认证中心在 `treadstone/api/auth.py`、`treadstone/api/deps.py`、`treadstone/core/users.py` 和 `treadstone/models/api_key.py`。

## 当前实现范围

### 1. 账户体系

当前账户模型以 `User` 为核心：

- `id`
- `email`
- `username`
- `role`
- `is_active`
- `is_superuser`
- `is_verified`
- `gmt_created` / `gmt_updated` / `gmt_deleted`

补充模型：

- `OAuthAccount`：记录 Google / GitHub OAuth 绑定
- `ApiKey`：长期凭证，数据库只存哈希和预览值
- `ApiKeySandboxGrant`：当 API Key 的数据面模式为 `selected` 时，记录它被授权访问的 sandbox 列表

### 2. 当前可用登录方式

当前代码真正可用的登录方式有两类：

- **邮箱 + 密码**
- **Google / GitHub OAuth**

其中 OAuth 主要服务于三种入口：

- 浏览器登录页
- CLI 浏览器授权页
- 通用 `/v1/auth/{provider}/authorize|callback` 流程

### 3. 控制面与数据面凭证边界

当前边界已经比较清晰：

- **控制面**：接受 `session cookie` 或 `API Key`
- **数据面**：只接受 `API Key`

这意味着：

- `/v1/sandboxes/*`、`/v1/auth/*`、`/v1/usage/*` 等控制面接口可以用 cookie 或 API key
- `/v1/sandboxes/{sandbox_id}/proxy/*` 明确拒绝 cookie，只接受 API key

API Key 的权限模型是：

- `control_plane: true|false`
- `data_plane.mode: none|all|selected`
- `data_plane.sandbox_ids: [...]` 仅在 `selected` 时生效

### 4. 当前角色模型

数据库里保留了三种角色：

- `admin`
- `rw`
- `ro`

但当前代码里真正有强制权限差异的，主要只有 `admin`：

- `/v1/admin/*`
- `/v1/audit/events`
- `/v1/auth/users`
- `/v1/auth/users/{user_id}` 删除

`rw` / `ro` 目前仍然是持久化字段，便于后续细化授权，但尚未形成完整的读写权限矩阵。

## 核心接口

### 用户与会话

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET /v1/auth/user`
- `POST /v1/auth/change-password`

当前注册行为有两个重要约束：

- **第一个注册用户自动成为 `admin`**
- 注册成功后会直接写入 session cookie，相当于自动登录

### 用户管理

- `GET /v1/auth/users`
- `DELETE /v1/auth/users/{user_id}`

### API Key

- `POST /v1/auth/api-keys`
- `GET /v1/auth/api-keys`
- `PATCH /v1/auth/api-keys/{key_id}`
- `DELETE /v1/auth/api-keys/{key_id}`

当前 API Key 的实现特点：

- 明文 key 只在创建时返回一次
- 数据库存 `key_hash` 和 `key_preview`
- 支持过期时间、控制面开关、数据面模式和选定 sandbox 授权

### 前端配置发现

- `GET /v1/config`

这个接口返回的是“当前服务允许哪些登录入口”，而不是抽象愿景。当前真实返回的 `login_methods` 由是否配置 Google / GitHub OAuth 决定，默认总会包含 `email`。

## 当前代码现状与边界

### 已经移除的历史设计

以下概念在旧文档里出现过，但已经不再是当前实现的一部分：

- 邀请注册
- Sandbox Token 作为独立用户凭证
- API Key 明文持久化

### 已存在但明确禁用的模式

配置项里仍能看到：

- `auth0`
- `authing`
- `logto`

但 `validate_runtime_settings()` 会在运行时直接 fail-fast 阻止这些模式启用。也就是说，**外部 OIDC Bearer 主认证并不是当前可用功能**。

### 文档维护建议

后续如果角色权限开始细化，应该优先更新这里，而不是再补一份新的“Phase 1 认证设计”。

