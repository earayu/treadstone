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
