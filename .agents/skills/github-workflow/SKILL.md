---
name: github-workflow
description: GitHub 协作工作流。创建 issue、PR、查看 CI 状态、管理分支时使用此 skill。适用于 AI agent 自动化 GitHub 操作。
---

# GitHub Workflow

本项目使用 `gh` CLI 与 GitHub 交互。所有常用操作已封装到 Makefile。

## 创建 Issue

```bash
make issue TITLE="bug: health check fails on timeout" BODY="详细描述" LABELS="bug"
```

LABELS 可选，常用标签：`bug`, `enhancement`, `documentation`

也可直接用 `gh`：

```bash
gh issue create --title "标题" --body "描述" --label "bug"
gh issue list
gh issue view 123
```

## 创建 Pull Request

```bash
# 方式一：Makefile（自动 push 当前分支）
make pr TITLE="feat: add user auth" BODY="## Summary\n- 实现了用户认证\n\n## Test Plan\n- make test 通过"

# 方式二：gh CLI（更多控制）
git push -u origin HEAD
gh pr create --title "标题" --body "描述"
```

PR body 推荐格式：

```markdown
## Summary
- 改了什么，为什么改

## Test Plan
- [ ] make test 通过
- [ ] make lint 通过
```

## 查看 CI 状态

```bash
make ci-status                    # 当前分支最近 5 次运行
gh run list --limit 10            # 全局最近 10 次
gh run view <run-id>              # 查看具体运行详情
gh run view <run-id> --log-failed # 查看失败日志
```

## 查看 PR

```bash
make pr-list                      # 列出所有打开的 PR
gh pr view <number>               # 查看 PR 详情
gh pr checks <number>             # 查看 PR 的 CI 检查状态
gh pr merge <number> --squash     # 合并 PR（squash）
```

## 分支管理

```bash
git checkout -b feat/feature-name   # 创建功能分支
# ... 开发 ...
make ship MSG="feat: 描述"          # 提交并推送
make pr TITLE="feat: 描述"          # 创建 PR
```

分支命名规范：`feat/xxx`, `fix/xxx`, `chore/xxx`

## 典型 AI 工作流

完成一个功能的完整流程：

```bash
git checkout -b feat/user-auth
# ... 实现功能 ...
make test                          # 确保测试通过
make format                        # 格式化代码
make lint                          # 代码检查
make ship MSG="feat: add user authentication"
make pr TITLE="feat: add user authentication" BODY="实现了用户注册和登录"
make ci-status                     # 确认 CI 通过
```
