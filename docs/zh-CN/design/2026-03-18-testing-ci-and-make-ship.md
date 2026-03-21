# 测试体系、CI/CD 与 make ship 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立项目测试目录规范、pytest 配置、GitHub Actions CI 流水线，并新增 `make ship` 命令供 AI agent 一键 add/commit/push。

**Architecture:** 测试分三层：unit（纯逻辑，无 IO）、api（httpx ASGITransport，无需真实服务器）、integration（需要真实 Neon DB，CI 中跳过）。CI 用 GitHub Actions，触发条件为 push 和 PR。`make ship` 通过 git diff 生成 commit message 参数，由 AI 调用时传入 MSG。

**Tech Stack:** pytest, pytest-asyncio, pytest-cov, httpx, GitHub Actions, Make

---

### Task 1：测试目录结构重组

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/api/__init__.py`
- Create: `tests/integration/__init__.py`
- Move: `tests/test_health.py` → `tests/api/test_health.py`
- Modify: `tests/__init__.py`（保留）

**Step 1: 创建测试子目录和 conftest**

测试目录规范：

```
tests/
  conftest.py          # 共享 fixture（test client 等）
  unit/                # 纯逻辑测试，无 IO，无 DB，无网络
    __init__.py
    test_config.py     # 示例：测试配置加载
  api/                 # API 路由测试，用 httpx ASGITransport
    __init__.py
    test_health.py     # 已有，迁移过来
  integration/         # 需要真实 DB 连接的测试
    __init__.py
    test_db.py         # 示例：测试真实 Neon 连接
```

创建目录和 `__init__.py`：

```bash
mkdir -p tests/unit tests/api tests/integration
touch tests/unit/__init__.py tests/api/__init__.py tests/integration/__init__.py
```

**Step 2: 写 conftest.py（共享 fixture）**

```python
# tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

**Step 3: 迁移 test_health.py 到 tests/api/ 并使用 fixture**

```python
# tests/api/test_health.py
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_health_returns_db_field(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert "db" in resp.json()
```

删除旧文件：

```bash
rm tests/test_health.py
```

**Step 4: 运行测试确认迁移成功**

Run: `make test`

Expected: 2 passed

**Step 5: Commit**

```bash
git add tests/
git commit -m "refactor: reorganize tests into unit/api/integration directories"
```

---

### Task 2：添加 pytest-cov + 测试标记配置

**Files:**
- Modify: `pyproject.toml`

**Step 1: 添加 pytest-cov 依赖**

```bash
uv add --dev pytest-cov
```

**Step 2: 更新 pyproject.toml 中的 pytest 配置**

在 `[tool.pytest.ini_options]` 部分替换为：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: 需要真实数据库连接的集成测试",
]
addopts = "-m 'not integration' --tb=short"
```

说明：
- `testpaths` 明确指定测试目录
- `markers` 注册 `integration` 标记，避免 pytest 警告
- `addopts` 默认排除 integration 测试（CI 和本地 `make test` 都不跑），需要时用 `make test-all` 显式运行

**Step 3: 运行测试确认配置生效**

Run: `make test`

Expected: 2 passed（integration 测试被排除）

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add pytest-cov, configure test markers and testpaths"
```

---

### Task 3：写示例 unit 测试和 integration 测试

**Files:**
- Create: `tests/unit/test_config.py`
- Create: `tests/integration/test_db.py`

**Step 1: 写 unit 测试（纯逻辑，无 IO）**

```python
# tests/unit/test_config.py
def test_settings_defaults():
    from treadstone.config import Settings

    s = Settings(database_url="postgresql+asyncpg://x:y@host/db?sslmode=require")
    assert s.app_name == "treadstone"
    assert s.debug is False


def test_settings_env_prefix(monkeypatch):
    monkeypatch.setenv("TREADSTONE_APP_NAME", "test-app")
    monkeypatch.setenv("TREADSTONE_DATABASE_URL", "postgresql+asyncpg://x:y@host/db?sslmode=require")
    from importlib import reload

    import treadstone.config as cfg

    reload(cfg)
    assert cfg.settings.app_name == "test-app"
```

**Step 2: 运行 unit 测试**

Run: `uv run pytest tests/unit/ -v`

Expected: 2 passed

**Step 3: 写 integration 测试（需要真实 DB）**

```python
# tests/integration/test_db.py
import pytest
from sqlalchemy import text

from treadstone.core.database import engine


@pytest.mark.integration
async def test_neon_connection():
    """验证能连接到真实的 Neon 数据库"""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.integration
async def test_neon_version():
    """验证 PostgreSQL 版本"""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version()"))
        version = result.scalar()
        assert "PostgreSQL" in version
```

**Step 4: 运行全部测试确认标记生效**

```bash
# 默认不跑 integration
uv run pytest tests/ -v
```

Expected: 4 passed（2 unit + 2 api），integration 被跳过

```bash
# 显式跑 integration
uv run pytest tests/ -v -m integration
```

Expected: 2 passed（仅 integration）

**Step 5: Commit**

```bash
git add tests/
git commit -m "test: add unit and integration test examples with markers"
```

---

### Task 4：更新 Makefile 测试命令

**Files:**
- Modify: `Makefile`

**Step 1: 更新 Makefile**

将现有的 `test` target 替换，并新增 `test-all`、`test-unit`、`test-cov`：

```makefile
test: ## Run tests (excludes integration)
	uv run pytest tests/ -v

test-unit: ## Run unit tests only
	uv run pytest tests/unit/ -v

test-all: ## Run all tests including integration (needs real DB)
	uv run pytest tests/ -v -m ""

test-cov: ## Run tests with coverage report
	uv run pytest tests/ -v --cov=treadstone --cov-report=term-missing --cov-report=html
```

注意：`test-all` 用 `-m ""` 覆盖 pyproject.toml 中的 `addopts` 默认排除。

**Step 2: 将新 target 加入 .PHONY**

在 Makefile 顶部 `.PHONY` 行追加：`test-unit test-all test-cov`

**Step 3: 验证**

```bash
make test
make test-unit
```

Expected: 各自通过

**Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: add test-unit, test-all, test-cov makefile targets"
```

---

### Task 5：GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: 写 CI 配置**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v6

      - run: uv sync --frozen

      - name: Ruff check
        run: uv run ruff check treadstone/ tests/

      - name: Ruff format check
        run: uv run ruff format --check treadstone/ tests/

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v6

      - run: uv sync --frozen

      - name: Run tests
        run: uv run pytest tests/ -v --cov=treadstone --cov-report=term-missing
        env:
          TREADSTONE_DATABASE_URL: "postgresql+asyncpg://fake:fake@localhost/fake?sslmode=require"

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t treadstone-api:ci .
```

说明：
- `lint` → `test` → `build` 三阶段串行
- test 阶段注入假的 DATABASE_URL（unit 和 api 测试不需要真实 DB）
- integration 测试被 `addopts = "-m 'not integration'"` 自动排除
- 使用 `astral-sh/setup-uv@v6` 官方 action 安装 uv

**Step 2: Commit**

```bash
git add .github/
git commit -m "ci: github actions workflow with lint, test, and build"
```

---

### Task 6：`make ship` 命令

**Files:**
- Modify: `Makefile`

**Step 1: 在 Makefile 末尾追加 ship target**

```makefile
ship: ## AI commit & push: make ship MSG="feat: add user model"
	@if [ -z "$(MSG)" ]; then echo "Usage: make ship MSG=\"your commit message\""; exit 1; fi
	git add -A
	git commit -m "$(MSG)"
	git push
```

**Step 2: 将 `ship` 加入 .PHONY**

在 Makefile 顶部 `.PHONY` 行追加：`ship`

**Step 3: 验证 help 输出**

Run: `make help`

Expected: 看到 `ship` 及其说明

**Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: add make ship for AI-driven commit and push"
```

---

### Task 7：更新 AGENTS.md 和 dev-workflow skill

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/dev-workflow/SKILL.md`

**Step 1: 更新 AGENTS.md Essential Commands 部分**

将 Essential Commands 部分替换为：

```markdown
## Essential Commands

所有项目命令通过 Makefile 暴露，运行 `make help` 查看全部。

```bash
make dev             # 启动本地开发服务器 (热重载)
make test            # 运行测试（排除 integration）
make test-unit       # 仅运行 unit 测试
make test-all        # 运行全部测试（含 integration，需真实 DB）
make test-cov        # 运行测试 + 覆盖率报告
make lint            # 代码检查
make format          # 自动格式化
make migrate         # 运行数据库迁移
make migration MSG=x # 生成新迁移
make build           # 构建 Docker 镜像
make ship MSG=x      # AI 专用：add + commit + push（MSG 必填）
```
```

**Step 2: 更新 AGENTS.md Testing 部分**

将 Testing 部分替换为：

```markdown
## Testing

- pytest-asyncio，asyncio_mode = "auto"（无需手动标记 @pytest.mark.asyncio）
- 用 httpx.AsyncClient + ASGITransport 测试 API（无需启动真实服务器）
- 测试中用 monkeypatch 设置环境变量，不依赖 .env 文件
- 测试三层结构：
  - `tests/unit/` — 纯逻辑，无 IO
  - `tests/api/` — API 路由测试，用 ASGITransport
  - `tests/integration/` — 需要真实 DB，标记 @pytest.mark.integration，默认不运行
- 共享 fixture 放在 `tests/conftest.py`（如 httpx client）
```

**Step 3: 在 dev-workflow SKILL.md 追加 ship 用法**

在 SKILL.md 末尾（`git commit` 那行之后）追加：

```markdown

## AI 提交代码

完成开发后，用 `make ship` 一键提交并推送：

```bash
make ship MSG="feat: 描述你的改动"
```

MSG 参数必填，遵循 Conventional Commits 规范。
```

**Step 4: Commit**

```bash
git add AGENTS.md .agents/skills/dev-workflow/SKILL.md
git commit -m "docs: update AGENTS.md and dev-workflow skill with test structure and make ship"
```

---

### Task 8：全量验证

**Step 1: 运行测试**

```bash
make test
```

Expected: 4 passed（2 unit + 2 api）

**Step 2: 运行 lint**

```bash
make lint
```

Expected: All checks passed

**Step 3: 验证 CI 配置格式**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>/dev/null || uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

如果没有 PyYAML 也没关系，CI 配置在 push 后由 GitHub 验证。

**Step 4: 验证 make ship（dry run）**

```bash
make help | grep ship
```

Expected: 看到 `ship — AI commit & push: make ship MSG="feat: add user model"`

**Step 5: 最终 Commit**

```bash
git add -A
git commit -m "chore: final cleanup for testing and CI setup"
```

---

## 测试目录规范速查

```
tests/
├── conftest.py              # 共享 fixture（client 等）
├── unit/                    # 纯逻辑，无 IO
│   ├── __init__.py
│   └── test_config.py       # 配置加载测试
├── api/                     # API 路由测试
│   ├── __init__.py
│   └── test_health.py       # 健康检查测试
└── integration/             # 需要真实 DB
    ├── __init__.py
    └── test_db.py           # Neon 连接测试
```

**放置规则：**
- 新增 model/service 逻辑 → `tests/unit/test_<模块名>.py`
- 新增 API 路由 → `tests/api/test_<路由名>.py`
- 需要真实 DB → `tests/integration/test_<场景>.py`，加 `@pytest.mark.integration`
- 跨模块共享的 fixture → `tests/conftest.py`

## CI/CD 流水线

```
push/PR to main
    ↓
┌─────────┐    ┌──────────┐    ┌─────────┐
│  lint   │ →  │   test   │ →  │  build  │
│ ruff    │    │ pytest   │    │ docker  │
│ check   │    │ + cov    │    │ build   │
└─────────┘    └──────────┘    └─────────┘
```

## make ship 用法

```bash
# AI agent 改完代码后调用
make ship MSG="feat: add user registration endpoint"
make ship MSG="fix: handle null email in auth"
make ship MSG="refactor: extract db session fixture"
```
