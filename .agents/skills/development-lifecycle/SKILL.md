---
name: development-lifecycle
description: Treadstone 功能开发的完整生命周期。从创建分支到合并 PR，每次开发新功能、修复 bug、重构代码时都应参考此 skill。涵盖分支策略、TDD 开发循环、代码质量、提交、PR 创建、CI 监控、合并。这是日常开发的主要参考。
---

# 开发生命周期

## 概览

每个功能/修复的完整路径：

```
创建分支 → TDD 开发循环 → 提交 → 创建 PR → CI 通过 → 合并
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

每次提交前：

```bash
make format    # 自动修复 import 顺序、格式
make lint      # 确认无问题（应该无输出）
```

---

## Step 4：提交

```bash
make ship MSG="feat: add user registration endpoint"
```

`make ship` = `git add -A` + `git commit` + `git push`。

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

## Step 5.5：维护 GitHub Project Board

每个 PR 创建后，需要关联到项目看板：

```bash
# 将 PR 添加到 Project Board（项目编号 5）
gh project item-add 5 --owner earayu --url <PR_URL>
```

同理，创建的 Issue 也要添加到看板。确保看板及时反映当前进度。

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

CI 流水线：`lint` → `test` → `build`，任一失败都需要修复后重新 push。

---

## Step 7：合并

CI 全绿后：

```bash
gh pr merge --squash    # squash 合并，保持 main 历史整洁
git checkout main && git pull
```

---

## 数据库变更（如有）

如果这个功能需要修改数据库 schema，在 Step 2 开发循环中：

```bash
# 修改 treadstone/models/ 后
make migration MSG="add users and oauth_accounts tables"
make migrate
```

出问题：`make downgrade` 回滚，修改模型后重新生成迁移。

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
| `make test-all` | 全部测试（含 integration） |
| `make format` | 自动格式化 |
| `make lint` | 代码检查 |
| `make migration MSG=x` | 生成 Alembic 迁移 |
| `make migrate` | 应用迁移 |
| `make downgrade` | 回滚上一次迁移 |
| `make ship MSG=x` | add + commit + push |
