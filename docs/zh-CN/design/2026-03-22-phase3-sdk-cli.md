# Phase 3: Python SDK + CLI

日期：2026-03-22

## 背景

Phase 2 沙箱编排已完成，OpenAPI 审查优化已落地。API surface 已稳定，是生成 SDK 和构建 CLI 的最佳时机。

SDK + CLI 是 Agent-Native 平台的用户入口——Agent 通过 SDK 调用，人类通过 CLI 操作。

## 目标

1. 从 OpenAPI spec 自动生成 Python SDK（`openapi-python-client`）
2. 基于 SDK 用 `click` 构建 CLI，完整覆盖所有 API（proxy 除外）
3. 为未来 TypeScript SDK 等多语言扩展预留目录结构

## 架构

```
┌──────────────────────────────────────────────────────────┐
│ FastAPI App (Code-first)                                  │
│   make gen-openapi → openapi.json                        │
├──────────────────────────────────────────────────────────┤
│ SDK 生成层                                                │
│   make gen-sdk → sdk/python/ (openapi-python-client)     │
│                  sdk/typescript/ (future)                 │
├──────────────────────────────────────────────────────────┤
│ CLI 层                                                    │
│   treadstone/cli/ (click, 依赖 SDK)                      │
│   $ treadstone sandboxes create --template aio-sandbox-tiny│
├──────────────────────────────────────────────────────────┤
│ 用户层                                                    │
│   AI Agent (通过 SDK) / 人类 (通过 CLI / REST)            │
└──────────────────────────────────────────────────────────┘
```

## 前置：修复 OpenAPI 问题

在生成 SDK 之前，需要修复两个 OpenAPI spec 的问题。

### 问题一：Proxy 端点排除

**现状**：`sandbox_proxy.py` 使用 `api_route` 对 5 个 HTTP method（GET/POST/PUT/DELETE/PATCH）注册同一个函数 `http_proxy`，导致 OpenAPI 导出时产生 5 个同名 operationId `sandbox-proxy-http_proxy`，codegen 工具无法处理重复 ID。

**分析**：Proxy 端点本质是透传请求到沙箱 Pod，属于"数据面"而非"控制面"。SDK 用户通过 sandbox 详情中的 `urls.proxy` 字段拿到完整 URL 后，直接用 httpx 调用即可，不需要 SDK 封装。

**方案**：在 proxy 路由上设置 `include_in_schema=False`，将其从 OpenAPI spec 中排除。

**改动文件**：`treadstone/api/sandbox_proxy.py`

改动前：

```python
@router.api_route(
    "/{sandbox_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def http_proxy(...):
```

改动后：

```python
@router.api_route(
    "/{sandbox_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def http_proxy(...):
```

**影响**：
- Proxy 功能不变，API 路由继续工作
- 仅从 OpenAPI spec（以及生成的 SDK）中移除
- Subdomain proxy（中间件层）不受影响

### 问题二：自写 login/logout 路由替换 fastapi-users 内置路由

**现状**：`auth.py` 第 32 行通过 `router.include_router(fastapi_users.get_auth_router(auth_backend))` 引入 login/logout 端点。fastapi-users 库内部给路由设置了 `name=f"auth:{backend.name}.login"` 格式的函数名。

经过 `custom_generate_unique_id`（格式：`{tag}-{route.name}`）后，生成的 operationId 为：
- `auth-auth:cookie.login`
- `auth-auth:cookie.logout`

**问题**：
1. 冒号 `:` 和点号 `.` 在 SDK codegen 中不合法——Python 函数名不允许这些字符，生成器要么报错要么生成无法使用的方法名
2. `auth-auth:` 前缀语义重复
3. 使用第三方库的内置路由失去了对错误格式的控制——login 失败时返回 `{"detail": "LOGIN_BAD_CREDENTIALS"}` 而非我们统一的 `{"error": {"code": ..., "message": ..., "status": ...}}` 格式
4. Request/Response schema 不受我们控制——login 使用 `OAuth2PasswordRequestForm`（form-urlencoded），这在某些场景下不如 JSON body 方便

**方案**：删除 `include_router(fastapi_users.get_auth_router(...))` 调用，自己实现 login 和 logout 端点，与其他端点风格一致。

**改动文件**：
- `treadstone/api/auth.py` — 替换 include_router 为自写 login/logout
- `treadstone/api/schemas.py` — 新增 `LoginRequest` / `LoginResponse` schema
- `treadstone/core/users.py` — 可能需要暴露 `get_user_manager` 给 auth router

**改动详情**：

#### 1. 新增 Schema（`treadstone/api/schemas.py`）

```python
class LoginRequest(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["MySecretPass123!"])

class LoginResponse(BaseModel):
    detail: str = Field(..., examples=["Login successful"])
```

注：login 的核心 side-effect 是 Set-Cookie，响应体是次要的。

#### 2. 自写 login 端点（`treadstone/api/auth.py`）

删除：

```python
# ── fastapi-users built-in login / logout ──
router.include_router(fastapi_users.get_auth_router(auth_backend))
```

替换为：

```python
from fastapi import Request, Response
from fastapi_users.password import PasswordHelper

from treadstone.api.schemas import LoginRequest, LoginResponse
from treadstone.core.users import auth_backend, get_jwt_strategy


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with email + password, set session cookie."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.unique().scalar_one_or_none()

    if user is None or not user.is_active:
        raise BadRequestError("Invalid email or password")

    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(body.password, user.hashed_password)
    if not valid:
        raise BadRequestError("Invalid email or password")

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    response = Response(
        content='{"detail":"Login successful"}',
        media_type="application/json",
    )
    response.set_cookie(
        key="session",
        value=token,
        max_age=86400,
        httponly=True,
        samesite="lax",
        secure=False,  # True in production with HTTPS
    )
    return response


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Clear the session cookie."""
    response = Response(
        content='{"detail":"Logout successful"}',
        media_type="application/json",
    )
    response.delete_cookie(key="session")
    return response
```

#### 3. 暴露 `get_jwt_strategy`（`treadstone/core/users.py`）

`get_jwt_strategy` 已经在 `core/users.py` 中定义，只需确认从 `auth.py` 可以 import。当前代码中 `get_jwt_strategy` 是模块级函数，可以直接 import。

#### 4. 关键行为变更

| 方面 | 之前（fastapi-users） | 之后（自写） |
|------|----------------------|-------------|
| **operationId** | `auth-auth:cookie.login` | `auth-login` |
| **请求格式** | `application/x-www-form-urlencoded`（username + password） | `application/json`（email + password） |
| **错误格式** | `{"detail": "LOGIN_BAD_CREDENTIALS"}` | `{"error": {"code": "bad_request", "message": "...", "status": 400}}` |
| **login 参数名** | `username`（实际传 email） | `email`（语义明确） |
| **logout** | 需要有效的 session cookie 才能调用 | 无条件清除 cookie（幂等） |

#### 5. 测试影响

需要更新以下测试文件：

- **`tests/api/test_auth_api.py`**：
  - `test_login_success`：请求体从 `data={"username": "...", "password": "..."}` 改为 `json={"email": "...", "password": "..."}`
  - `test_login_wrong_password`：同上
  - `test_get_user_after_login`：同上

- **`tests/integration/test_auth_integration.py`**：同样更新 login 调用方式

- **`tests/e2e/01-auth-flow.hurl`** 到 **`05-sandbox-dual-path.hurl`**：所有 login 步骤从 `[FormParams]` 改为 `Content-Type: application/json` + JSON body

- **所有 API 测试中的 `auth_client` fixture**：统一改用 JSON body

E2E 测试改动示例：

```hurl
# 之前
POST {{base_url}}/v1/auth/login
[FormParams]
username: {{email}}
password: {{password}}

# 之后
POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email}}",
    "password": "{{password}}"
}
```

---

## Step 1: Python SDK

### 选型

`openapi-python-client`（MIT 开源）

- 原生 httpx + async/sync 双模式
- 生成独立可发布的 Python 包
- 模型用 attrs（类型标注完整）
- 自带 ruff 格式化 post-hook

### 目录结构

```
sdk/
  python/
    treadstone_sdk/         # generated package
      api/
        auth/
        sandboxes/
        sandbox_templates/
        ...
      models/
      client.py
    pyproject.toml          # standalone, pip-installable
    README.md
```

### 生成配置

项目根目录添加 `openapi-client-config.yaml`：

```yaml
project_name_override: treadstone-sdk
package_name_override: treadstone_sdk
post_hooks:
  - "ruff check --fix ."
  - "ruff format ."
```

### Makefile target

```makefile
gen-sdk: gen-openapi ## Generate Python SDK from OpenAPI spec
	openapi-python-client generate \
		--path openapi.json \
		--config openapi-client-config.yaml \
		--output-path sdk/python \
		--overwrite
```

### .gitignore 策略

- `openapi.json` 保持 gitignored（构建产物）
- `sdk/python/` 纳入版本库（便于 review 和直接 pip install）

---

## Step 2: CLI

### 选型

- `click`：Python CLI 事实标准
- `rich`：Rich table output

### 入口

`treadstone/cli/main.py` + pyproject.toml `[project.scripts]` 注册 `treadstone` 命令。

### 目录结构

```
treadstone/
  cli/
    __init__.py
    main.py          # click group 入口
    auth.py          # login, logout, register, whoami, change-password, invite, users, delete-user
    api_keys.py      # create, list, delete
    sandboxes.py     # create, list, get, delete, start, stop, token
    templates.py     # list
    config_cmd.py    # show
    _client.py       # SDK client factory（从 env/config 读取 API key）
    _output.py       # table/json 输出格式化
```

### 命令树

```
treadstone
  auth
    login              POST /v1/auth/login
    logout             POST /v1/auth/logout
    register           POST /v1/auth/register
    whoami             GET  /v1/auth/user
    change-password    POST /v1/auth/change-password
    invite             POST /v1/auth/invite
    users              GET  /v1/auth/users
    delete-user        DELETE /v1/auth/users/:id
  api-keys
    create             POST /v1/auth/api-keys
    list               GET  /v1/auth/api-keys
    delete             DELETE /v1/auth/api-keys/:id
  templates
    list               GET  /v1/sandbox-templates
  sandboxes (alias: sb)
    create             POST /v1/sandboxes
    list               GET  /v1/sandboxes
    get                GET  /v1/sandboxes/:id
    delete             DELETE /v1/sandboxes/:id
    start              POST /v1/sandboxes/:id/start
    stop               POST /v1/sandboxes/:id/stop
    token              POST /v1/sandboxes/:id/token
  config
    show               GET  /v1/config
  health               GET  /health
```

### 认证配置

CLI 从以下位置读取认证信息（按优先级排序）：

1. 命令行参数 `--api-key` / `--base-url`
2. 环境变量 `TREADSTONE_API_KEY` / `TREADSTONE_BASE_URL`
3. 配置文件 `~/.config/treadstone/config.toml`

```toml
# ~/.config/treadstone/config.toml
[default]
api_key = "sk-..."
base_url = "http://localhost:8000"
```

### 输出格式

- 默认：Rich table（human-friendly）
- `--json` flag：JSON 输出（agent-friendly，方便管道处理）

### 依赖

pyproject.toml 新增：

```toml
[project.scripts]
treadstone = "treadstone.cli.main:cli"

dependencies = [
    # ... existing ...
    "click>=8.1",
    "rich>=14.0",
]
```

---

## 最终 operationId 一览

修复后的完整 OpenAPI operationId 列表：

```
auth-login                                POST /v1/auth/login
auth-logout                               POST /v1/auth/logout
auth-register                             POST /v1/auth/register
auth-get_user                             GET  /v1/auth/user
auth-list_users                           GET  /v1/auth/users
auth-delete_user                          DELETE /v1/auth/users/:id
auth-change_password                      POST /v1/auth/change-password
auth-invite                               POST /v1/auth/invite
auth-create_api_key                       POST /v1/auth/api-keys
auth-list_api_keys                        GET  /v1/auth/api-keys
auth-delete_api_key                       DELETE /v1/auth/api-keys/:id
sandboxes-create_sandbox                  POST /v1/sandboxes
sandboxes-list_sandboxes                  GET  /v1/sandboxes
sandboxes-get_sandbox                     GET  /v1/sandboxes/:id
sandboxes-delete_sandbox                  DELETE /v1/sandboxes/:id
sandboxes-start_sandbox                   POST /v1/sandboxes/:id/start
sandboxes-stop_sandbox                    POST /v1/sandboxes/:id/stop
sandboxes-create_sandbox_token_endpoint   POST /v1/sandboxes/:id/token
sandbox-templates-list_sandbox_templates  GET  /v1/sandbox-templates
config-get_config                         GET  /v1/config
system-health                             GET  /health
```

（proxy 端点已排除）

---

## 后续扩展

- **TypeScript SDK**：从同一份 `openapi.json` 用 `openapi-typescript-codegen` 或 `openapi-fetch` 生成，放在 `sdk/typescript/`
- **其他语言 SDK**：同样基于 OpenAPI spec，独立生成
- **CI 验证**：`gen-openapi` → `gen-sdk` → lint 通过，确保 spec 与代码同步
