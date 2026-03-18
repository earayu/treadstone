---
name: dev-workflow
description: Treadstone 本地开发工作流。首次设置、启动服务、测试、lint、数据库迁移、添加依赖、提交代码时使用此 skill。这是日常开发的核心参考，涵盖从 clone 到 commit 的全流程。
---

# Dev Workflow

## 首次设置

```bash
make install                    # uv sync 安装依赖
cp .env.example .env            # 填入 Neon 连接串
make migrate                    # 应用数据库迁移
make test                       # 验证环境正常
```

## 常用命令速查

| 命令 | 作用 |
|------|------|
| `make dev` | 启动开发服务器（localhost:8000，热重载） |
| `make test` | 运行测试（排除 integration） |
| `make test-unit` | 仅 unit 测试 |
| `make test-all` | 全部测试（含 integration，需真实 DB） |
| `make test-cov` | 测试 + 覆盖率报告 |
| `make lint` | 代码检查（不修改） |
| `make format` | 自动修复 + 格式化 |
| `make migration MSG="..."` | 生成 Alembic 迁移（MSG 必填） |
| `make migrate` | 应用迁移 |
| `make downgrade` | 回滚上一次迁移 |
| `make ship MSG="..."` | git add -A + commit + push（MSG 必填） |

API 文档：http://localhost:8000/docs

## 测试结构

```
tests/
├── conftest.py        # 共享 fixture（client 等）
├── unit/              # 纯逻辑，无 IO
├── api/               # API 路由测试，用 httpx ASGITransport
└── integration/       # 需真实 DB，标记 @pytest.mark.integration
```

新增测试时按类型放到对应目录。integration 测试默认不运行，需 `make test-all`。

## 新增 API 端点（TDD）

1. `tests/api/test_xxx.py` 写失败测试
2. `make test` 确认失败
3. `treadstone/api/xxx.py` 实现路由
4. `make test` 确认通过
5. `make format && make lint`
6. `make ship MSG="feat: ..."`

## 数据库变更

修改 `treadstone/models/` 后：

```bash
make migration MSG="add users table"
make migrate
```

出问题可以 `make downgrade` 回滚，改完模型后重新生成。

## 添加依赖

```bash
uv add <package>              # 运行时依赖
uv add --dev <package>        # 开发依赖
```

添加后提交 `pyproject.toml` 和 `uv.lock`。
