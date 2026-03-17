---
name: dev-workflow
description: Treadstone 开发工作流。涵盖首次设置、本地开发、测试、lint、数据库迁移、依赖管理、提交代码的完整流程。开发、测试、迁移数据库时使用此 skill。
---

# Dev Workflow

## 首次设置

```bash
make install         # 安装依赖 (uv sync)
cp .env.example .env # 创建 .env，填入 Neon 连接串
make migrate         # 应用数据库迁移
make test            # 验证一切正常
```

Neon 连接串从 https://console.neon.tech 获取，格式：
`postgresql+asyncpg://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`

## 本地开发

```bash
make dev             # 启动开发服务器 (localhost:8000, 热重载)
```

API 文档：http://localhost:8000/docs

## 测试

```bash
make test            # 运行测试（排除 integration）
make test-unit       # 仅 unit 测试
make test-all        # 全部测试（含 integration，需真实 DB）
make test-cov        # 测试 + 覆盖率报告
```

测试三层结构：
- `tests/unit/` — 纯逻辑，无 IO，放 model/service 的测试
- `tests/api/` — API 路由测试，用 httpx ASGITransport（不需要真实服务器）
- `tests/integration/` — 需要真实 DB，标记 `@pytest.mark.integration`

共享 fixture 在 `tests/conftest.py`，已有 `client` fixture。

## 代码质量

```bash
make lint            # 检查（不修改）
make format          # 自动修复 + 格式化
```

提交前必须通过 lint。

## 数据库迁移

```bash
make migration MSG="add users table"  # 生成迁移（MSG 必填）
make migrate                          # 应用迁移
make downgrade                        # 回滚上一次迁移
```

Alembic 使用 sync driver（psycopg2），自动将 `+asyncpg` 替换掉。

## 依赖管理

```bash
uv add <package>           # 添加运行时依赖
uv add --dev <package>     # 添加开发依赖
uv sync                    # 同步依赖（等同于 make install）
```

添加依赖后记得提交 `pyproject.toml` 和 `uv.lock`。

## 新增 API 端点的标准流程

1. 在 `tests/api/` 写失败测试
2. `make test` 确认失败
3. 在 `treadstone/api/` 实现路由
4. `make test` 确认通过
5. `make format` 自动格式化
6. `make lint` 确认代码质量
7. 提交

## 提交代码

```bash
make ship MSG="feat: add user registration"
```

`make ship` = git add -A + commit + push。MSG 必填，遵循 Conventional Commits。
