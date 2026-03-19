# Treadstone

Sandbox + Skills 组合为可复用垂直 Agent 的开放平台与市场。

## Tech Stack

- Python 3.12+, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg
- Database: Neon (Serverless PostgreSQL)
- Package manager: uv
- Linter/formatter: ruff
- Testing: pytest + pytest-asyncio + httpx
- Containerization: Docker
- Orchestration: Kubernetes (Kind for dev, GKE/EKS/AKS for prod)

## Project Structure

```
treadstone/          # 应用源码
  main.py            # FastAPI 入口
  config.py          # pydantic-settings 配置
  core/              # 数据库、共享工具
  models/            # SQLAlchemy 模型
  api/               # API 路由
  auth/              # 认证
  services/          # 业务逻辑
tests/               # pytest 测试
alembic/             # 数据库迁移
deploy/              # K8s manifests
docs/                # 设计文档和计划
.agents/skills/      # AI Agent 可复用 skill
```

## Essential Commands

所有项目命令通过 Makefile 暴露，运行 `make help` 查看全部。

```bash
# Development
make install         # 安装依赖 (首次设置)
make dev             # 启动本地开发服务器 (热重载)

# Testing
make test            # 运行测试（排除 integration）
make test-unit       # 仅运行 unit 测试
make test-all        # 运行全部测试（含 integration，需真实 DB）
make test-cov        # 运行测试 + 覆盖率报告

# Code Quality
make lint            # 代码检查
make format          # 自动格式化

# Database
make migrate         # 运行数据库迁移
make migration MSG=x # 生成新迁移（MSG 必填）
make downgrade       # 回滚上一次迁移

# OpenAPI / SDK
make gen-openapi     # 导出 openapi.json（不需要启动服务器）

# Build
make build           # 构建 Docker 镜像

# Git & GitHub
make ship MSG=x      # add + commit + push（MSG 必填，仅限功能分支）
```

GitHub 操作直接使用 `gh` CLI。

**Skills：**
- `.agents/skills/dev-setup/` — 首次设置本地环境（只需一次）
- `.agents/skills/development-lifecycle/` — 日常功能开发生命周期（每次开发参考）

## Code Conventions

- 用开发者的语言和开发者沟通，注释、commit message用英语。文档默认用中文放在docs/zh-CN目录。
- **GitHub 上所有公开内容必须使用英文**：commit messages, PR title/body, Issue title/body, review comments, release notes。
- Async everywhere: 所有 DB 操作、HTTP 调用、API handler 必须 async
- TDD: 先写失败测试 → 实现 → 验证通过
- DRY, YAGNI: 不做过早抽象
- 所有函数签名必须有 type hints
- Ruff rules: E, F, I, UP (见 pyproject.toml)
- 行宽: 120

## Database

- Neon Serverless PostgreSQL，连接串通过 TREADSTONE_DATABASE_URL 环境变量注入
- SQLAlchemy async engine + asyncpg driver
- Alembic 迁移（alembic 使用 sync URL，需去掉 +asyncpg）
- 所有连接串必须带 ?sslmode=require（asyncpg 端通过 ssl context 处理，非 URL 参数）

## Testing

- pytest-asyncio，asyncio_mode = "auto"（无需手动标记 @pytest.mark.asyncio）
- 用 httpx.AsyncClient + ASGITransport 测试 API（无需启动真实服务器）
- 测试中用 monkeypatch 设置环境变量，不依赖 .env 文件
- 测试三层结构：
  - `tests/unit/` — 纯逻辑，无 IO
  - `tests/api/` — API 路由测试，用 ASGITransport
  - `tests/integration/` — 需要真实 DB，标记 @pytest.mark.integration，默认不运行
- 共享 fixture 放在 `tests/conftest.py`（如 httpx client）

## OpenAPI / SDK Generation

- Code-first: 从 FastAPI 代码自动生成 OpenAPI spec，不维护静态 YAML
- `make gen-openapi` 导出 `openapi.json`（构建产物，已加入 .gitignore）
- 所有 API router 必须设置 `tags=["xxx"]`，SDK 方法名依赖 tag + 函数名
- 未来生成前端 TypeScript SDK：`npx @hey-api/openapi-ts -i openapi.json -o src/client`
- 未来生成 Python SDK：`openapi-python-client generate --path openapi.json`

## Git Workflow

- **永远不要直接 push 到 main 分支**，所有合并必须走 Pull Request
- Conventional commits: feat:, fix:, chore:, docs:, test:, refactor:
- 频繁提交，每个 commit 是一个小的逻辑单元
- 绝不提交 .env、secrets 或凭证
- 每个 PR 创建后，关联到 GitHub Project Board: `gh project item-add 5 --owner earayu --url <PR_URL>`
- PR/Issue 创建后应在 Project Board（https://github.com/users/earayu/projects/5/views/1）中维护状态

## Cursor Cloud specific instructions

### Services overview

Treadstone is a single FastAPI backend service. It requires:
- **Neon PostgreSQL** (external) — set `TREADSTONE_DATABASE_URL` secret for DB-dependent features (auth, sandboxes, migrations). Without it, unit/API tests still pass (they use in-memory SQLite), the dev server starts, and `/health` works, but auth and CRUD endpoints return 500.
- **Kubernetes** — not needed for local dev. `TREADSTONE_DEBUG=true` activates `FakeK8sClient`.

### Running the dev environment

1. `make install` installs all deps via `uv sync` and configures git hooks.
2. Copy `.env.example` to `.env` (already has `TREADSTONE_DEBUG=true`). Set `TREADSTONE_DATABASE_URL` if you have a Neon connection string.
3. `make dev` starts uvicorn on port 8000 with hot reload.
4. The k8s_sync background task will log DB connection errors on startup if no real DB is configured — this is expected and does not prevent the server from serving non-DB endpoints.

### Testing caveats

- `make test` runs unit + API tests (137+) using in-memory SQLite — no real DB needed.
- `make test-all` includes integration tests that require `TREADSTONE_DATABASE_URL` pointing to a real Neon instance.
- API tests override DB session via `app.dependency_overrides` with `sqlite+aiosqlite://`. If you add new API tests needing DB, follow the same pattern in `tests/api/test_auth_api.py`.

### Lint / format

- `make lint` (ruff check + format check), `make format` (auto-fix). See Makefile for details.

### K8s cluster in Cloud Agent VM

Kind does **not** work in Cloud Agent VMs (Firecracker) — systemd and kernel features are missing. Use **k3s** directly instead:

```bash
# Install k3s binary (skip systemd service registration)
curl -sfL https://get.k3s.io | INSTALL_K3S_SKIP_START=true sh -

# Start k3s server-only (no agent — avoids cgroup/overlayfs issues)
sudo k3s server \
  --disable traefik --disable metrics-server \
  --write-kubeconfig-mode 644 --data-dir /tmp/k3s \
  --snapshotter fuse-overlayfs --flannel-backend host-gw \
  --kubelet-arg=cgroups-per-qos=false \
  --kubelet-arg=enforce-node-allocatable="" \
  --disable-agent &>/tmp/k3s-server.log &

# Copy kubeconfig
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

Key caveats:
- **Server-only mode** (`--disable-agent`): K8s API works for CRDs/resources, but no Pods can be scheduled (no nodes). The agent-sandbox controller won't run as a Pod.
- **fuse-overlayfs** is required (kernel doesn't support overlayfs).
- **host-gw** flannel backend is needed (VXLAN not supported by kernel).
- To run Treadstone against the real K8s API, set `TREADSTONE_DEBUG=false` in `.env` and unset the `TREADSTONE_DEBUG` env var if it was exported in the shell.
- Sandbox creation via API works (creates SandboxClaim in K8s), but sandboxes stay in "creating" state without a running controller.
