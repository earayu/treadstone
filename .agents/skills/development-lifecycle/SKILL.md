---
name: development-lifecycle
description: Treadstone 功能开发的完整生命周期。从创建分支到合并 PR，每次开发新功能、修复 bug、重构代码时都应参考此 skill。涵盖分支策略、TDD 开发循环、代码质量、提交、PR 创建、CI 监控、合并。这是日常开发的主要参考。
---

# 开发生命周期

## 核心规则

> **永远不要直接 push 到 main 分支。** 所有代码合并必须通过 Pull Request。
> 这包括 AI Agent 在内 —— `make ship` 只应在功能分支上使用，不要在 main 上执行。

## 概览

每个功能/修复的完整路径：

```
创建分支 → TDD 开发循环 → make ship → 创建 PR → CI 自动验证 → 合并
```

---

## Step 1：创建功能分支

从最新的 main 开始：

```bash
git checkout main && git pull
git checkout -b feat/user-authentication
```

分支命名：`feat/xxx`、`fix/xxx`、`chore/xxx`、`refactor/xxx`

---

## Step 2：TDD 开发循环

每个功能单元重复这个循环，保持小步快跑：

**① 写失败测试**

按类型放到正确目录：
- `tests/unit/` — 纯逻辑（model、service、helper），无 IO
- `tests/api/` — API 路由测试，用 httpx ASGITransport
- `tests/integration/` — 需要真实 DB，加 `@pytest.mark.integration`

```python
# 例：tests/api/test_auth.py
async def test_register_returns_201(client):
    resp = await client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "Pass123!"
    })
    assert resp.status_code == 201
```

**② 确认测试失败**

```bash
make test
# Expected: FAILED — 模块或路由不存在
```

**③ 写最小实现让测试通过**

只写让当前测试通过的代码，不多写。

**④ 确认测试通过**

```bash
make test
# Expected: PASSED
```

**⑤ 重构（如需要）**

清理代码，`make test` 确认仍然通过。

---

## Step 3：代码质量

pre-commit hook 会在每次 `git commit` 时自动执行 format + lint，无需手动运行。

如需手动触发：`make format`（自动修复）、`make lint`（检查）。

---

## Step 4：提交

```bash
make ship MSG="feat: add user registration endpoint"
```

`make ship` = `git add -A` + `git commit` + `git push`（push 到当前功能分支，不是 main）。

> **⚠️ 提交前确认当前分支不是 main！** `git branch --show-current` 应返回 `feat/xxx` 之类的分支名。

**Commit message 格式：** `<type>: <description>`
- `feat:` new feature
- `fix:` bug fix
- `test:` tests
- `refactor:` refactoring
- `chore:` config, dependencies
- `docs:` documentation

小步提交，每个 commit 一个逻辑单元。

> **⚠️ 语言规范：所有 GitHub 上公开可见的内容必须使用英文。** 包括但不限于：
> - Commit messages
> - PR title 和 body
> - Issue title 和 body
> - Code review comments
> - Release notes
>
> 代码注释和本地文档（docs/zh-CN/）使用中文。AGENTS.md 中已有此规范，此处再次强调。

---

## Step 5：创建 Pull Request

```bash
gh pr create --title "feat: add user authentication" --body "$(cat <<'EOF'
## Summary
- Implement user registration and login
- Support email/password + Cookie session

## Test Plan
- [x] make test
- [x] make lint
EOF
)"
```

PR body 用 HEREDOC 传，避免引号转义问题。**PR title 和 body 必须使用英文。**

---

## Step 5.5：GitHub Project Board

PR 和 Issue 创建后会被 GitHub Actions（`.github/workflows/project.yml`）自动添加到 [Project Board](https://github.com/users/earayu/projects/5/views/1)，无需手动操作。

---

## Step 6：监控 CI

```bash
gh run watch                                    # 实时跟踪当前分支最新 CI 运行
gh run list --branch "$(git branch --show-current)"  # 查看历史运行
```

**CI 失败时的排查流程：**

```bash
gh run view <run-id> --log-failed   # 只看失败的 job 日志
make test                           # 本地复现
make lint                           # 检查格式问题
```

CI 流水线：`lint` + `test`（并行）+ `integration`（仅 PR）→ `build`，任一失败都需要修复后重新 push。

---

## Step 7：合并

CI 全绿后：

```bash
gh pr merge --squash    # squash 合并，保持 main 历史整洁
git checkout main && git pull
```

---

## 集成测试（如涉及数据库交互）

集成测试跑在真实的 Neon test 分支上，详细说明见 `tests/integration/README.md`。

快速开始：

```bash
cp tests/integration/.env.test.example tests/integration/.env.test
# 编辑 .env.test，填入 Neon test 分支连接串
make test-integration    # 仅集成测试
make test-all            # 全部测试含集成
```

---

## 数据库变更（如有）

涉及数据库 schema 变更时，参考 `.agents/skills/database-migration/` skill，它包含完整的模型设计规范、迁移生成、Neon 分支测试、回滚流程和常见陷阱。

快速命令：

```bash
# 修改 treadstone/models/ 后
make migration MSG="add users and oauth_accounts tables"
make migrate          # 先在 test 分支验证，再应用到 production
make downgrade        # 出问题时回滚
```

---

## 添加依赖（如有）

```bash
uv add <package>           # 运行时依赖
uv add --dev <package>     # 开发依赖
```

添加后，`pyproject.toml` 和 `uv.lock` 一起提交。

---

## 快速参考：所有开发命令

| 命令 | 用途 |
|------|------|
| `make dev` | 启动开发服务器（localhost:8000，热重载） |
| `make test` | 运行测试（排除 integration） |
| `make test-unit` | 仅 unit 测试 |
| `make test-api` | 仅 API 测试 |
| `make test-integration` | 仅集成测试（需真实 DB） |
| `make test-all` | 全部测试（含 integration） |
| `make format` | 自动格式化 |
| `make lint` | 代码检查 |
| `make migration MSG=x` | 生成 Alembic 迁移 |
| `make migrate` | 应用迁移 |
| `make downgrade` | 回滚上一次迁移 |
| `make gen-openapi` | 导出 openapi.json（不启动服务器） |
| `make up` | 端到端环境搭建 + 部署（local: kind + build + load + deploy） |
| `make down` | 拆除环境（local: undeploy + kind delete） |
| `make ship MSG=x` | add + commit + push（仅限功能分支） |

---

## OpenAPI 与 SDK 生成

项目采用 Code-first 策略：从 FastAPI 代码自动生成 OpenAPI spec，不维护静态 YAML。

### 添加新 API 时的规范

所有 `APIRouter` 必须设置 `tags` 参数，SDK 方法名由 `tag-函数名` 组合生成：

```python
router = APIRouter(prefix="/api/sandboxes", tags=["sandboxes"])

@router.post("/")
async def create_sandbox(...):  # → SDK: SandboxesService.create_sandbox()
    ...
```

### 导出 OpenAPI spec

```bash
make gen-openapi    # 输出 openapi.json（已在 .gitignore 中，不进 git）
```

### 生成前端 TypeScript SDK（未来）

```bash
npx @hey-api/openapi-ts -i openapi.json -o frontend/src/client
```

### 生成 Python SDK（未来）

```bash
openapi-python-client generate --path openapi.json
```
