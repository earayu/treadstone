# CLI 浏览器 OAuth 登录设计

**日期：** 2026-03-26  
**状态：** 已实现  
**关联 PR：** [#85 feat: CLI browser OAuth login flow](https://github.com/earayu/treadstone/pull/85)  
**前置 PR：** [#80 feat: OAuth social login and invitation removal](https://github.com/earayu/treadstone/pull/80)

## 背景

PR #80 完成了 Google/GitHub OAuth 的服务端和浏览器登录集成，但 CLI 的认证登录（`treadstone auth login`）仍然只支持邮箱密码方式。这是 Phase 2 的核心任务：让 CLI 也能通过浏览器完成 OAuth 登录。

同时，这个项目的 CLI 存在两类使用者：

1. **人类开发者**：在终端里运行命令，可以与浏览器交互
2. **AI Agent**：在自动化脚本中调用，不能与浏览器交互

这两类使用者的认证需求完全不同，设计需要同时照顾到两者。

## 核心决策

### 人类开发者：浏览器优先的 OAuth 登录

`treadstone auth login`（无参数）默认走浏览器登录流程，与 `gh auth login`、`vercel login`、`claude`（Anthropic CLI）等主流开发工具体验一致：

1. CLI 创建一个短时 login flow，向服务端申请登录票据
2. CLI 自动打开浏览器，访问登录页
3. 用户在浏览器中选择 Google / GitHub / 邮箱登录
4. 登录成功后，CLI 感知到并保存 session，用户可以关闭浏览器

> **不使用 localhost 回调服务器**：部分早期工具（如早期 gcloud）会在本地启动 HTTP server 接收 OAuth 回调。这种方式在 SSH 连接、容器、WSL 等远程场景下会失败，还需要固定端口。  
> 轮询方案（`gh`、`vercel` 使用的方式）无论本地还是远程都能正常工作——用户可以在另一台机器的浏览器上完成登录。

### AI Agent：API Key（现有机制，无需修改）

AI Agent 应该使用 API Key，而非 OAuth。

- 人类开发者通过 CLI 登录后，创建一个专属 API Key 交给 Agent
- Agent 通过 `TREADSTONE_API_KEY` 环境变量或 `--api-key` flag 使用
- 这是业界标准（OpenAI、Anthropic、Vercel、GitHub 等均采用此模式）

**OAuth 本身就是最好的防滥用机制**：Google/GitHub 登录天然需要人类介入，不需要额外的邮箱验证码、CAPTCHA 等。

### 邮箱密码直登：保留

`treadstone auth login --email X --password Y` 不变，继续走服务端的 `/v1/auth/login`。这为脚本化场景（如 CI/CD）保留了退路。

## 完整流程

```
CLI                        Server                  Browser             IdP
 |                            |                       |                  |
 |-- POST /v1/auth/cli/flows ->|                       |                  |
 |<-- {flow_id, secret, url} --|                       |                  |
 |                            |                       |                  |
 | 打印 URL + 尝试打开浏览器  |                       |                  |
 |                            |                       |                  |
 | 开始轮询...                |                       |                  |
 |                            |<-- GET /v1/auth/cli/login?flow_id=xxx ----|
 |                            |-- HTML 登录页 -------->|                  |
 |                            |                       |                  |
 |                            |    [用户选择 Google]   |                  |
 |                            |<-- GET /google/authorize?cli_flow_id=xxx -|
 |                            |-- 重定向到 Google ---->|----> Google      |
 |                            |<----------- Google 回调 code --------------|
 |                            | 创建/关联用户          |                  |
 |                            | 标记 flow approved    |                  |
 |                            |-- "可以关闭浏览器" --->|                  |
 |                            |                       |                  |
 |-- GET /flows/{id}/status --|                       |                  |
 |<-- {status: "approved"} ---|                       |                  |
 |-- POST /flows/{id}/exchange|                       |                  |
 |<-- {session_token: "eyJ..."}                       |                  |
 |                            |                       |                  |
 | 保存到 session.json        |                       |                  |
 | 输出"Login successful"     |                       |                  |
```

## 实现方案

### 1. 数据模型：`cli_login_flow` 表

新增 `CliLoginFlow` 模型（`treadstone/models/cli_login_flow.py`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `String(24)` | 主键，前缀 `clf`，公开可见 |
| `flow_secret_hash` | `String(64)` | flow secret 的 SHA-256 哈希，原始值不存储 |
| `status` | `String(16)` | `pending` / `approved` / `used` / `expired` |
| `user_id` | `String(24)`, FK nullable | 批准后设置 |
| `provider` | `String(16)`, nullable | `google` / `github` / `email`，批准后设置 |
| `gmt_created` | `DateTime(tz)` | 创建时间 |
| `gmt_expires` | `DateTime(tz)` | 过期时间，默认创建后 10 分钟 |
| `gmt_completed` | `DateTime(tz)` nullable | 批准时间 |

**Secret 哈希策略**：使用 SHA-256（而非 bcrypt），因为 flow secret 是高熵随机值（`secrets.token_urlsafe(32)`），不需要慢哈希来防止暴力破解。

**`expired` 状态是懒计算的**：数据库中不存储 `expired` 状态值；轮询时如果 `status == pending` 且 `utc_now() > gmt_expires`，则在内存中返回 `expired`。

### 2. CLI 认证 API（`treadstone/api/cli_auth.py`）

路由前缀 `/v1/auth/cli`，标签 `auth`。

| 方法 | 路径 | 说明 | 是否暴露在 OpenAPI |
|------|------|------|------|
| `POST` | `/flows` | 创建 login flow | ✅ |
| `GET` | `/flows/{flow_id}/status` | 轮询状态（需 `X-Flow-Secret` header） | ✅ |
| `POST` | `/flows/{flow_id}/exchange` | 换取 session token（需 `X-Flow-Secret` header） | ✅ |
| `GET` | `/login` | 渲染 CLI 登录 HTML 页 | ❌ `include_in_schema=False` |
| `POST` | `/login` | 处理邮箱密码表单提交 | ❌ `include_in_schema=False` |

**`X-Flow-Secret` 安全设计**：
- Secret 通过 HTTP header 传输，不放在 URL query string（避免写入访问日志）
- 服务端只存哈希，原始 secret 仅在创建时返回一次
- 错误返回 401，不区分"流程不存在"与"secret 错误"（防止枚举）

**Exchange 单次性**：exchange 成功后立即将 flow 标记为 `used`，防止重复换取。

### 3. OAuth 流程扩展（`treadstone/api/auth.py`）

在现有 OAuth state JWT 中新增可选字段 `cli_flow_id`。

**授权阶段**：`GET /v1/auth/google/authorize?cli_flow_id=xxx`，将 `cli_flow_id` 编码进 state JWT（与现有 `return_to` 互斥）。

**回调阶段**：`_oauth_callback` 检测 state 中是否存在 `cli_flow_id`：
- 存在：创建/关联用户 → 标记 flow approved → 返回 CLI 成功页（**不设置 session cookie**，session 通过 exchange 下发）
- 不存在：走现有逻辑（browser 流程或 API 流程）

`surface` 字段在 CLI 流程中记录为 `"cli"`，用于审计日志区分。

### 4. 共享登录页渲染器（`treadstone/services/login_page.py`）

提取 `render_login_page()` 和 `render_success_page()` 两个函数，供 `browser.py` 和 `cli_auth.py` 共同复用，避免 HTML 模板分叉维护。

`render_login_page()` 参数化了：
- `title` / `subtitle`：不同入口显示不同文案
- `form_action`：表单提交地址
- `hidden_fields`：隐藏字段（browser 传 `return_to`，CLI 传 `flow_id`）
- `google_authorize_params` / `github_authorize_params`：OAuth 按钮参数（browser 传 `return_to`，CLI 传 `cli_flow_id`）

### 5. CLI 命令更新（`cli/treadstone_cli/auth.py`）

`login` 命令的 `--email` 和 `--password` 由 `required=True` 改为 `default=None`：

| 参数组合 | 行为 |
|---------|------|
| 无参数 | 浏览器 OAuth 流程 |
| 提供 `--email` + `--password` | 直接邮箱密码登录（现有逻辑不变） |
| 只提供 `--email` | 提示输入密码 |
| 只提供 `--password` | 报错 `UsageError` |
| `--json` 模式无凭证 | 返回 JSON 错误，立即退出，不进入交互 |

浏览器流程的 CLI 逻辑：
1. `POST /v1/auth/cli/flows` 获取 flow
2. 打印 URL，调用 `webbrowser.open()`（失败则只打印，不中断）
3. 每 2 秒轮询一次 status，最多等待 10 分钟
4. 收到 `approved` → exchange → 保存 session → 输出成功
5. 收到 `expired` 或 `used` → 提示错误，退出码 1
6. 超时（300 次轮询）→ 提示超时，退出码 1

## 审计日志

| 事件 | `action` | `surface` |
|------|----------|-----------|
| CLI 邮箱密码登录成功 | `auth.login` | `cli` |
| CLI OAuth 登录成功（Google/GitHub） | `auth.login` | `cli` |
| CLI OAuth 首次注册 | `auth.register` | `cli` |
| CLI OAuth 邮箱自动关联 | `auth.oauth.link` | `cli` |
| CLI 邮箱密码登录失败 | `auth.login`（result: failure） | `cli` |

flow 创建和 exchange 本身不产生审计日志（登录审计在 approve 阶段完成）。

## 边界和不在范围内的内容

- **本期 session TTL 不变**：仍为 24 小时，无 refresh token
- **Flow TTL**：10 分钟，过期不可续期，重新 `treadstone auth login` 即可
- **不做 localhost 回调服务器**：轮询方案在所有场景下兼容性更好
- **不自动生成 API Key**：登录完成后由用户手动 `treadstone api-keys create`
- **过期 flow 清理**：懒清理（轮询时判断），不做定期清理任务（可后续按需加）
- **邮箱验证码**：当前注册无验证码要求；由于 OAuth 路径天然需要人类操作 Google/GitHub 账号，已具备防滥用能力

## 文件变更汇总

| 文件 | 变更 |
|------|------|
| `treadstone/models/cli_login_flow.py` | 新增 |
| `treadstone/models/__init__.py` | 新增 CliLoginFlow 导出 |
| `alembic/versions/2457b93fc846_add_cli_login_flow_table.py` | 新增 |
| `treadstone/api/cli_auth.py` | 新增 |
| `treadstone/services/login_page.py` | 新增 |
| `treadstone/api/auth.py` | 扩展 OAuth state 支持 `cli_flow_id` |
| `treadstone/api/browser.py` | 重构为使用共享渲染器 |
| `treadstone/main.py` | 注册 cli_auth router |
| `cli/treadstone_cli/auth.py` | 更新 login 命令 |
| `tests/api/test_cli_auth_api.py` | 新增 |
| `tests/api/test_oauth_api.py` | 修复 monkeypatch 目标（移至 login_page_service） |
