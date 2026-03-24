# 认证边界加固与校验收紧设计归档

**日期：** 2026-03-24  
**状态：** 已实现  
**关联 Issue：** [#60 Harden sandbox subdomain Web UI with browser-scoped sessions](https://github.com/earayu/treadstone/issues/60)

## 背景

Treadstone 需要同时服务人类开发者与 AI Agent。随着 Sandbox 控制面、数据面、CLI、SDK 与 API Key 能力逐步成型，原有认证模型暴露出几个核心问题：

1. `Sandbox Token` 被混入通用 `get_current_user` 依赖链，实际上可以访问控制面。
2. API Key 以明文存储，数据库泄露会直接导致长期凭证泄露。
3. 数据面与控制面的凭证边界不清晰，浏览器子域名入口也缺少后续安全设计。
4. 多个输入模型校验偏宽松，容易把无效输入推进业务层。

这次改动的目标不是引入完整 RBAC / service account / browser session，而是先把 v1 的边界收紧到一个清晰、可维护、可继续演进的状态。

## 最终决策

### 1. 三类凭证保留，但职责明确

- **Cookie / API Key**：控制面凭证。
- **Sandbox Token**：数据面凭证，仅限短期、单 Sandbox、单用途。
- **浏览器子域名会话**：本轮不实现，后续单独设计。

当前刻意保留的 v1 取舍：

- API Key 与 Cookie 在控制面上保持等权。
- 不在本轮引入细粒度 API Key scope。
- 不在本轮引入 organization / workspace / service account。

### 2. 控制面与数据面依赖彻底拆分

新增两类依赖：

- `get_current_control_plane_user`
  - 接受 Cookie 或 API Key
  - 如果请求显式带了非法 Bearer，不再静默回落到 Cookie，而是直接返回 `401 auth_invalid`
- `get_current_sandbox_token_user`
  - 仅接受 Sandbox Token
  - Cookie / API Key 访问数据面时返回 `401 auth_invalid`

同时在 `request.state` 中记录 `credential_type`，为日志、审计和后续策略扩展预留统一入口。

### 3. Sandbox Token 只保留数据面能力

- `GET /v1/sandboxes/{id}` 不再接受 Sandbox Token
- `POST /v1/sandboxes/{id}/token` 只能由控制面凭证调用
- `/{sandbox_id}/proxy/*` 成为当前唯一接受 Sandbox Token 的 API 路径

这样可以防止“用数据面令牌反向进入控制面”或“用 Sandbox Token 再铸造新 token”的权限升级路径。

### 4. API Key 改为哈希存储

数据库层从：

- `key`（明文）

变更为：

- `key_hash`
- `key_preview`

行为约定：

- 创建 API Key 时仍然只返回一次完整 secret
- 列表接口仅返回 `key_preview`
- 鉴权时对入参 secret 做哈希后比对

这次迁移是**单向安全迁移**。由于哈希不可逆，Alembic `downgrade()` 明确标记为不可恢复明文 secret。

### 5. 请求模型与查询参数全面收紧

本轮统一做了“尽量让坏输入尽早失败”的校验收紧：

- `email` 改用 `EmailStr`
- `role` 改为 `Role` 枚举
- `CreateSandboxTokenRequest.expires_in` 限制为 `1..86400`
- `CreateApiKeyRequest.expires_in` 限制为 `1..31536000`
- `labels` 改为 `dict[str, str]`
- `label` 查询参数必须符合 `key:value`
- `auto_stop_interval >= 1`
- `auto_delete_interval == -1 or >= 1`
- `storage_size` 必须是合法 K8s 容量格式，且仅允许在 `persist=true` 时出现

额外处理：

- 邀请码里如果存在非法 `role`，现在返回受控错误，而不是 500
- `Invitation.is_valid()` 兼容 SQLite 测试环境里的 naive datetime

### 6. 模板目录改为公开只读

`GET /v1/sandbox-templates` 改为匿名可读。

原因：

- 当前模板是平台内置 catalog，不属于租户私有资源
- 公开只读能降低 CLI/SDK/Agent 的接入摩擦
- 若未来引入私有模板，再显式区分“公开模板”和“私有模板”

### 7. 不安全的子域名入口先 fail-fast

本轮明确**不支持**公网 `sandbox_domain` Web UI 入口。

策略：

- 允许本地开发域名，如 `localhost` / `*.localhost`
- 非本地域名一律在运行时配置校验阶段拒绝启动

原因：

- 当前子域名直通模型缺少浏览器专用会话设计
- 如果继续开放，会绕过“数据面仅 Sandbox Token”这次刚建立的边界

后续浏览器会话方案单独追踪：Issue [#60](https://github.com/earayu/treadstone/issues/60)

### 8. 外部 OIDC Bearer 模式改为 fail-fast

之前配置层允许 `auth0` / `authing` / `logto`，但主体验证映射并未真正完成，存在“看起来支持、实际上不可用”的问题。

因此本轮采取保守策略：

- 运行时配置校验直接拒绝这些模式
- 等 principal mapping、用户绑定和完整鉴权链完成后再重新开放

## 已落地的接口语义变化

### 控制面

- `GET /v1/auth/user`：仅 Cookie / API Key
- `POST /v1/auth/api-keys`：仅 Cookie / API Key
- `GET /v1/sandboxes/{id}`：仅 Cookie / API Key
- `POST /v1/sandboxes/{id}/token`：仅 Cookie / API Key

### 数据面

- `GET|POST|PUT|DELETE|PATCH /v1/sandboxes/{id}/proxy/{path}`：仅 Sandbox Token

### 公共只读

- `GET /v1/sandbox-templates`：匿名可读

## 测试与验证

本轮新增或更新了以下测试类别：

- Sandbox Token 不能访问控制面
- Cookie / API Key 不能访问数据面代理
- Sandbox Token scope mismatch 返回 `403`
- API Key 明文不再写入数据库
- 非法 email / role / expires / label / storage 配置返回 `422`
- 非本地 `sandbox_domain`、默认/过短 `jwt_secret`、未完成的 OIDC 模式在配置校验时失败
- 模板列表允许匿名访问

本地验证结果：

- `uv run pytest -q` 通过
- `uv run ruff check treadstone tests cli` 通过

## 后续工作

### 优先级最高

- 设计并实现浏览器子域名会话 / launch ticket / host-only cookie 方案  
  追踪：[#60](https://github.com/earayu/treadstone/issues/60)

### 后续可继续演进

- 为 API Key 引入细粒度 scope
- 引入 service account / machine identity
- 重新设计并接通外部 OIDC principal mapping
- 增加认证审计日志与 credential_type 观测面板
