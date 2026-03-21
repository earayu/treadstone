# Phase 3: Python SDK + CLI 实施计划

日期：2026-03-22
设计文档：[`docs/zh-CN/design/2026-03-22-phase3-sdk-cli.md`](../design/2026-03-22-phase3-sdk-cli.md)

## 实施步骤

### Step 0: 前置修复

#### 0.1 排除 Proxy 端点

- 文件：`treadstone/api/sandbox_proxy.py`
- 改动：在 `@router.api_route(...)` 上添加 `include_in_schema=False`
- 验证：`make gen-openapi` 不再有 `Duplicate Operation ID` 警告，且输出的 `openapi.json` 中不包含 proxy 路径

#### 0.2 自写 login/logout 替换 fastapi-users 内置路由

- 文件：`treadstone/api/auth.py`
  - 删除 `router.include_router(fastapi_users.get_auth_router(auth_backend))`
  - 新增 `login` 端点：JSON body（`LoginRequest: {email, password}`），认证逻辑参考 fastapi-users 源码，使用 `PasswordHelper` 验证密码，使用 `get_jwt_strategy().write_token(user)` 生成 JWT，通过 `Response.set_cookie()` 设置 session cookie
  - 新增 `logout` 端点：无条件清除 session cookie，幂等操作
  - 错误统一用 `BadRequestError`（不再抛 `HTTPException`）

- 文件：`treadstone/api/schemas.py`
  - 新增 `LoginRequest(email, password)` 和 `LoginResponse(detail)`

- 文件：`treadstone/core/users.py`
  - 确认 `get_jwt_strategy` 可被 `auth.py` import（已满足）

- 测试更新：
  - `tests/api/test_auth_api.py`：login 调用从 `data={"username": ..., "password": ...}` 改为 `json={"email": ..., "password": ...}`
  - `tests/api/test_sandboxes_api.py`、`test_sandbox_templates_api.py`、`test_sandbox_token_api.py`、`test_api_key_api.py`：`auth_client` fixture 中的 login 调用同步修改
  - `tests/integration/test_auth_integration.py`：login 调用同步修改
  - `tests/e2e/01-auth-flow.hurl` ~ `05-sandbox-dual-path.hurl`：所有 login 步骤从 FormParams 改为 JSON body
  - `tests/api/test_deps.py`：无需修改（不涉及 login）

- 验证：`make test` 全部通过，`make gen-openapi` 输出中 login operationId 为 `auth-login`、logout 为 `auth-logout`

### Step 1: Python SDK 生成

#### 1.1 安装 codegen 工具

```bash
uv tool install openapi-python-client
```

或作为 dev 依赖添加到 pyproject.toml（推荐前者，codegen 是构建工具而非运行时依赖）。

#### 1.2 创建配置文件

创建 `openapi-client-config.yaml`：

```yaml
project_name_override: treadstone-sdk
package_name_override: treadstone_sdk
post_hooks:
  - "ruff check --fix ."
  - "ruff format ."
```

#### 1.3 添加 Makefile target

在 `Makefile` 的 `# ── OpenAPI / SDK` 部分添加：

```makefile
gen-sdk: gen-openapi ## Generate Python SDK from OpenAPI spec
	openapi-python-client generate \
		--path openapi.json \
		--config openapi-client-config.yaml \
		--output-path sdk/python \
		--overwrite
```

#### 1.4 首次生成并验证

```bash
make gen-sdk
cd sdk/python && uv run python -c "import treadstone_sdk"
```

验证：
- `sdk/python/` 目录生成成功
- package 可以 import
- `ruff check sdk/python/` 无报错

#### 1.5 纳入版本库

- `sdk/python/` 纳入 git（非 gitignore）
- `openapi.json` 保持 gitignore

### Step 2: CLI 实现

#### 2.1 添加依赖

在 `pyproject.toml` 的 `dependencies` 中添加：

```
"click>=8.1",
"rich>=14.0",
```

在 `[project.scripts]` 中添加：

```toml
[project.scripts]
treadstone = "treadstone.cli.main:cli"
```

运行 `uv sync`。

#### 2.2 创建 CLI 骨架

创建 `treadstone/cli/` 目录，包含：

- `__init__.py`（空）
- `main.py`：click group 根命令，注册所有子命令组，定义全局选项 `--json`、`--api-key`、`--base-url`
- `_client.py`：SDK client 工厂函数，按优先级读取：命令行参数 > 环境变量（`TREADSTONE_API_KEY`、`TREADSTONE_BASE_URL`）> 配置文件（`~/.config/treadstone/config.toml`）
- `_output.py`：输出格式化工具，支持 table（rich）和 JSON 两种模式

验证：`uv run treadstone --help` 输出帮助信息。

#### 2.3 实现 sandboxes 命令组

文件：`treadstone/cli/sandboxes.py`

命令列表：
- `treadstone sandboxes create --template <name> [--name <name>] [--labels key:val] [--persist] [--storage-size 10Gi]`
- `treadstone sandboxes list [--label key:val] [--limit N] [--offset N]`
- `treadstone sandboxes get <sandbox_id>`
- `treadstone sandboxes delete <sandbox_id>`
- `treadstone sandboxes start <sandbox_id>`
- `treadstone sandboxes stop <sandbox_id>`
- `treadstone sandboxes token <sandbox_id> [--expires-in 3600]`

注册别名 `sb`：`treadstone sb list` 等价于 `treadstone sandboxes list`。

#### 2.4 实现 templates 命令

文件：`treadstone/cli/templates.py`

- `treadstone templates list`

#### 2.5 实现 auth + api-keys 命令组

文件：`treadstone/cli/auth.py`

- `treadstone auth login --email <email> --password <password>`（也可交互式输入密码）
- `treadstone auth logout`
- `treadstone auth register --email <email> --password <password> [--invitation-token <token>]`
- `treadstone auth whoami`
- `treadstone auth change-password --old-password <old> --new-password <new>`
- `treadstone auth invite --email <email> [--role ro]`
- `treadstone auth users [--limit N] [--offset N]`
- `treadstone auth delete-user <user_id>`

文件：`treadstone/cli/api_keys.py`

- `treadstone api-keys create [--name <name>] [--expires-in <seconds>]`
- `treadstone api-keys list`
- `treadstone api-keys delete <key_id>`

#### 2.6 实现 config + health 命令

文件：`treadstone/cli/config_cmd.py`

- `treadstone config show`

在 `main.py` 中直接定义：

- `treadstone health`

### Step 3: 文档与 CI

#### 3.1 更新 README

- Quick Start 部分添加 CLI 安装和使用示例
- 添加 SDK 使用示例（Python 代码片段）
- 更新 Status 表格：Phase 3 标记为 Done

#### 3.2 更新 CI

在 `.github/workflows/ci.yml` 中添加一步：

```yaml
- name: Verify SDK generation
  run: |
    make gen-openapi
    # 验证 openapi.json 生成成功且无 warning
```

## 检查清单

- [ ] Proxy 端点从 OpenAPI spec 中排除
- [ ] login/logout 自写路由，operationId 为 `auth-login` / `auth-logout`
- [ ] login 请求改为 JSON body（`{email, password}`）
- [ ] 所有测试通过（unit + API + E2E）
- [ ] `make gen-openapi` 无 warning
- [ ] openapi-python-client 安装并配置
- [ ] `make gen-sdk` 生成 SDK 到 `sdk/python/`
- [ ] SDK 可 import 且 ruff 通过
- [ ] CLI 骨架创建，`treadstone --help` 可用
- [ ] sandboxes 命令组实现并可用
- [ ] templates 命令实现
- [ ] auth + api-keys 命令组实现
- [ ] config + health 命令实现
- [ ] README 更新
- [ ] CI 添加 SDK 生成验证
