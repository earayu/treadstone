# Phase 0：项目脚手架 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 搭建 Treadstone 项目基础结构，能本地启动 FastAPI 服务，连接 PostgreSQL，跑通健康检查接口。

**Architecture:** FastAPI + SQLAlchemy async + PostgreSQL，uv 管理依赖，Docker Compose 编排本地开发环境。

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy (async), asyncpg, Alembic, PostgreSQL 16, Docker Compose, uv, pytest, ruff

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
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/treadstone"

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
    monkeypatch.setenv("TREADSTONE_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/treadstone")
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

### Task 5：Docker Compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Step 1: 写 Dockerfile**

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

CMD ["uv", "run", "uvicorn", "treadstone.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: 写 docker-compose.yml**

```yaml
# docker-compose.yml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: treadstone
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      TREADSTONE_DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/treadstone
    depends_on:
      - db

volumes:
  pgdata:
```

**Step 3: 写 .env.example**

```bash
# .env.example
TREADSTONE_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/treadstone
TREADSTONE_DEBUG=true
```

**Step 4: 验证启动**

```bash
docker compose up -d
curl http://localhost:8000/health
```

Expected: `{"status":"ok","db":true}`

**Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml .env.example
git commit -m "chore: docker compose for local development"
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
