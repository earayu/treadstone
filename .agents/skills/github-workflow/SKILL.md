---
name: github-workflow
description: GitHub 协作工作流。创建 issue、PR、查看 CI 状态、review、合并 PR 时使用此 skill。当需要与 GitHub 交互时（issue、PR、CI、release），务必参考此 skill。
---

# GitHub Workflow

所有 GitHub 操作直接使用 `gh` CLI（项目已认证）。不要用 Makefile 封装——`gh` 的参数表达力更强，你已经很熟悉它了。

## Issue

```bash
gh issue create --title "标题" --body "描述" --label "bug"
gh issue list
gh issue view 42
gh issue close 42 --reason completed
```

常用标签：`bug`, `enhancement`, `documentation`

## Pull Request

### 创建 PR

```bash
git push -u origin HEAD
gh pr create --title "feat: add user auth" --body "$(cat <<'EOF'
## Summary
- 实现了什么，为什么

## Test Plan
- [ ] make test
- [ ] make lint
EOF
)"
```

用 HEREDOC 传 body 以确保多行格式正确。

### 查看与管理 PR

```bash
gh pr list
gh pr view 123
gh pr checks 123          # CI 检查状态
gh pr diff 123             # 查看 diff
gh pr merge 123 --squash   # squash 合并
```

## CI 状态

```bash
gh run list --branch "$(git branch --show-current)" --limit 5
gh run view <run-id>
gh run view <run-id> --log-failed   # 只看失败日志
gh run watch <run-id>               # 实时跟踪运行中的 CI
```

CI 失败时，先用 `--log-failed` 看日志，本地用 `make test && make lint` 复现。

## 完整功能开发流程

```bash
# 1. 创建分支
git checkout -b feat/user-auth

# 2. 开发（TDD 循环）
#    写测试 → make test 确认失败 → 实现 → make test 确认通过

# 3. 提交
make format
make ship MSG="feat: add user authentication"

# 4. 创建 PR
gh pr create --title "feat: add user authentication" --body "..."

# 5. 等 CI 通过
gh run watch

# 6. 合并
gh pr merge --squash
```

## 分支命名

- `feat/xxx` — 新功能
- `fix/xxx` — 修复
- `chore/xxx` — 基础设施、配置
