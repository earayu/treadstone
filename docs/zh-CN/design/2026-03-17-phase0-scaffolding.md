# Phase 0：项目脚手架 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建 Treadstone 项目基础结构，能本地启动 FastAPI 服务，连接 PostgreSQL，跑通健康检查接口。

**Architecture:** FastAPI + SQLAlchemy async + Neon (Serverless PostgreSQL)，uv 管理依赖，开发和生产统一使用 Neon 托管数据库，应用部署在 K8s 上。不使用 Docker Compose。

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg, Alembic, Neon (Serverless PostgreSQL), Docker, uv, pytest, ruff

---

### Task 1：初始化 uv 项目

**Files:**
- Create: `pyproject.toml`

**Step 1: 初始化项目**

```bash
uv init --name treadstone --python 3.12
```

**Step 2: 添加核心依赖**

```bash
uv add fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic-settings
```

**Step 3: 添加开发依赖**

```bash
uv add --dev pytest pytest-asyncio httpx ruff
```

**Step 4: 验证**

```bash
uv run python -c "import fastapi; print(fastapi.__version__)"
```

Expected: 打印 FastAPI 版本号

**Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: init uv project with core dependencies"
```

---

### Task 2：FastAPI 应用骨架

**Files:**
- Create: `treadstone/__init__.py`
- Create: `treadstone/main.py`
- Create: `treadstone/config.py`
- Test: `tests/__init__.py`
- Test: `tests/test_health.py`

**Step 1: 写健康检查的测试**

```python
# tests/test_health.py
import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

**Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_health.py -v
```

Expected: FAIL（模块不存在）

**Step 3: 实现配置模块**

```python
# treadstone/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "treadstone"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/treadstone?sslmode=require"

    model_config = {"env_prefix": "TREADSTONE_"}


settings = Settings()
```

**Step 4: 实现 FastAPI 应用**

```python
# treadstone/main.py
from fastapi import FastAPI

from treadstone.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_health.py -v
```

Expected: PASS

**Step 6: 验证本地启动**

```bash
uv run uvicorn treadstone.main:app --reload
```

访问 http://localhost:8000/health 和 http://localhost:8000/docs

**Step 7: Commit**

```bash
git add treadstone/ tests/
git commit -m "feat: fastapi app skeleton with health check"
```

---

### Task 3：数据库连接

**Files:**
- Create: `treadstone/core/__init__.py`
- Create: `treadstone/core/database.py`
- Modify: `treadstone/main.py`
- Test: `tests/test_health.py`（扩展）

**Step 1: 写 DB 健康检查测试**

```python
# tests/test_health.py（追加）
@pytest.mark.asyncio
async def test_health_with_db(monkeypatch):
    monkeypatch.setenv("TREADSTONE_DATABASE_URL", "postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/treadstone?sslmode=require")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert "db" in resp.json()
```

**Step 2: 实现数据库连接模块**

```python
# treadstone/core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from treadstone.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with async_session() as session:
        yield session
```

**Step 3: 更新 main.py 添加 DB 健康检查**

```python
# treadstone/main.py
from fastapi import FastAPI
from sqlalchemy import text

from treadstone.config import settings
from treadstone.core.database import engine

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db": db_ok}
```

**Step 4: Commit**

```bash
git add treadstone/core/ treadstone/main.py tests/
git commit -m "feat: async postgresql connection with health check"
```

---

### Task 4：Alembic 数据库迁移

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/`（空目录）

**Step 1: 初始化 Alembic**

```bash
uv run alembic init alembic
```

**Step 2: 修改 alembic/env.py**

将 `target_metadata` 设为 `Base.metadata`，将 `sqlalchemy.url` 改为从 `treadstone.config.settings` 读取。关键修改：

```python
# alembic/env.py 顶部
from treadstone.core.database import Base
from treadstone.config import settings

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))
```

**Step 3: Commit**

```bash
git add alembic.ini alembic/
git commit -m "chore: init alembic for db migrations"
```

---

### Task 5：Neon Database 配置 + Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.env.example`

**Step 1: 在 Neon Console 创建项目**

前往 https://console.neon.tech 创建项目：
- Project name: `treadstone`
- Region: 选离你最近的区域
- PostgreSQL version: 16

创建后获取连接串，格式如下：
```
postgresql+asyncpg://neondb_owner:xxxx@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

**Step 2: 写 .env.example**

```bash
# .env.example
# 从 Neon Console 获取连接串：https://console.neon.tech
TREADSTONE_DATABASE_URL=postgresql+asyncpg://user:password@ep-xxx.region.aws.neon.tech/treadstone?sslmode=require
TREADSTONE_DEBUG=true
```

**Step 3: 创建本地 .env 文件（不提交到 git）**

```bash
cp .env.example .env
# 编辑 .env，填入从 Neon Console 获取的真实连接串
```

**Step 4: 写 Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY treadstone/ treadstone/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "treadstone.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 5: 验证 Neon 连接**

```bash
# 加载 .env 后本地启动
uv run uvicorn treadstone.main:app --reload
curl http://localhost:8000/health
```

Expected: `{"status":"ok","db":true}`

**Step 6: 运行 Alembic 迁移（针对 Neon）**

```bash
uv run alembic upgrade head
```

Expected: 迁移成功（此时还没有 migration，仅验证连接可用）

**Step 7: Commit**

```bash
git add Dockerfile .env.example
git commit -m "chore: neon database config and dockerfile"
```

---

### Task 6：Ruff lint 配置 + .gitignore

**Files:**
- Modify: `pyproject.toml`（追加 ruff 配置）
- Create: `.gitignore`

**Step 1: 在 pyproject.toml 中添加 ruff 配置**

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 2: 写 .gitignore**

```gitignore
__pycache__/
*.py[cod]
.env
*.egg-info/
dist/
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
```

**Step 3: 运行 lint**

```bash
uv run ruff check treadstone/ tests/
uv run ruff format treadstone/ tests/
```

**Step 4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: ruff lint config and gitignore"
```

---

### Task 7：AI Agent 项目指令（AGENTS.md + .agents/skills/）

**Files:**
- Create: `AGENTS.md`
- Create: `.agents/skills/dev-workflow/SKILL.md`

两层配置各司其职：

| 文件 | 作用 | 支持平台 |
|------|------|---------|
| `AGENTS.md` | 项目总体约定（技术栈、规范、命令） | Cursor, Codex CLI, Copilot, Claude Code, Windsurf, Amp, Devin |
| `.agents/skills/` | 可复用工作流 skill | Cursor (原生), Claude Code (.claude/skills/ 兼容), Codex (.codex/skills/ 兼容) |

Cursor 原生从 `.agents/skills/` 加载 skill，同时兼容 `.claude/skills/` 和 `.codex/skills/`。因此 `.agents/skills/` 是最佳的平台无关位置。后续随项目发展可按需添加更多 skill（如 deploy、troubleshoot 等）。

**Step 1: 写 AGENTS.md**

`AGENTS.md` 是跨平台标准，作为项目级 AI 指令的唯一信息源。保持精简，只放 agent 需要知道的全局约定。

```markdown
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

## Essential Commands

所有项目命令通过 Makefile 暴露，运行 `make help` 查看全部。

  make dev             # 启动本地开发服务器 (热重载)
  make test            # 运行测试
  make lint            # 代码检查
  make format          # 自动格式化
  make migrate         # 运行数据库迁移
  make migration MSG=x # 生成新迁移
  make build           # 构建 Docker 镜像

## Code Conventions

- 用中文与开发者沟通（注释、文档、commit message）
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
- 所有连接串必须带 ?sslmode=require

## Testing

- pytest-asyncio，asyncio_mode = "auto"
- 用 httpx.AsyncClient + ASGITransport 测试 API（无需启动真实服务器）
- 测试中用 monkeypatch 设置环境变量，不依赖 .env 文件

## Git Workflow

- Conventional commits: feat:, fix:, chore:, docs:, test:, refactor:
- 频繁提交，每个 commit 是一个小的逻辑单元
- 绝不提交 .env、secrets 或凭证
```

**Step 2: 写第一个 skill — dev-workflow**

```markdown
---
name: dev-workflow
description: Treadstone 开发工作流。开发、测试、迁移数据库时使用此 skill。涵盖本地开发启动、测试运行、lint、数据库迁移的完整流程。
---

# Dev Workflow

## 本地开发

1. 确保 `.env` 文件存在且包含有效的 `TREADSTONE_DATABASE_URL`（Neon 连接串）
2. 启动开发服务器：`make dev`
3. API 文档：http://localhost:8000/docs

## 运行测试

```bash
make test
```

测试不需要真实数据库连接（用 httpx ASGITransport mock）。
需要数据库的集成测试用 monkeypatch 注入环境变量。

## 代码质量

```bash
make lint     # 检查（不修改）
make format   # 自动修复 + 格式化
```

提交前必须通过 lint。

## 数据库迁移

```bash
# 修改 models/ 后生成迁移
make migration MSG="描述变更"

# 应用迁移到 Neon
make migrate
```

注意：Alembic 使用 sync driver（psycopg2），会自动将 DATABASE_URL 中的 `+asyncpg` 替换掉。

## 新增 API 端点的标准流程

1. 在 `tests/` 写失败测试
2. `make test` 确认失败
3. 在 `treadstone/api/` 实现路由
4. `make test` 确认通过
5. `make lint` 确认代码质量
6. `git commit`
```

**Step 3: Commit**

```bash
git add AGENTS.md .agents/
git commit -m "chore: AGENTS.md and .agents/skills for AI agent instructions"
```

---

### Task 8：Makefile

**Files:**
- Create: `Makefile`

**Step 1: 写 Makefile**

```makefile
.PHONY: help dev test lint format migrate migration build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start local dev server with hot reload
	uv run uvicorn treadstone.main:app --reload --host 0.0.0.0 --port 8000

test: ## Run all tests
	uv run pytest tests/ -v

lint: ## Run linter and formatter check
	uv run ruff check treadstone/ tests/
	uv run ruff format --check treadstone/ tests/

format: ## Auto-format code
	uv run ruff check --fix treadstone/ tests/
	uv run ruff format treadstone/ tests/

migrate: ## Run database migrations
	uv run alembic upgrade head

migration: ## Generate new migration (usage: make migration MSG="add users table")
	uv run alembic revision --autogenerate -m "$(MSG)"

build: ## Build Docker image
	docker build -t treadstone-api:latest .

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/
```

**Step 2: 验证**

```bash
make help
```

Expected: 列出所有可用命令及说明

**Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: makefile for common dev commands"
```
