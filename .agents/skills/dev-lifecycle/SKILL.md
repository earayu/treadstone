---
name: dev-lifecycle
description: Treadstone daily development lifecycle — the step-by-step loop from creating a branch to merging a PR. Use this skill every time you develop a new feature, fix a bug, refactor code, or make any code change that will be shipped. Covers branching, TDD cycle, shipping, PR creation, CI monitoring, and merging. If the user says "add feature X", "fix bug Y", "implement Z", or anything that implies writing and shipping code, this skill applies.
---

# Development Lifecycle

Never push directly to main. All code merges go through Pull Requests — this includes AI Agents.

## The Loop

```
branch → TDD (write test → fail → implement → pass → refactor) → ship → PR → CI → merge
```

## Step 1: Create a Feature Branch

```bash
git checkout main && git pull
git checkout -b feat/descriptive-name
```

Branch naming: `feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/`.

## Step 2: TDD Cycle

Repeat per unit of work — keep iterations small. For docs-only changes, do not invent fake tests; instead verify examples against the source of truth (`Makefile`, CLI help, workflows, or code) and run lightweight checks such as `git diff --check`.

1. **Write a failing test** in the appropriate directory (`tests/unit/`, `tests/api/`, or `tests/integration/`). See the Testing section in `AGENTS.md` for which directory to use.

2. **Confirm it fails:**
   ```bash
   make test
   ```

3. **Write the minimal implementation** to make the test pass — nothing more.

4. **Confirm it passes:**
   ```bash
   make test
   ```

5. **Refactor** if needed, re-run `make test` to confirm nothing broke.

### Docs-Only Changes

For `README.md`, `AGENTS.md`, `.agents/skills/*/SKILL.md`, or similar documentation-only work:

- Still use a feature branch and PR
- Prefer `docs:` commit messages
- Validate commands and paths against the current repo before editing
- Run `git diff --check` before shipping

## Step 3: Ship to Feature Branch

```bash
make ship MSG="feat: add user registration endpoint"
```

This runs `git add -A && git commit && git push` on the current feature branch.

Verify you are NOT on main before shipping: `git branch --show-current`.

Commit messages follow Conventional Commits format (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `docs:`). Keep commits small — one logical unit each. See `AGENTS.md` Git Workflow section for full conventions.

All GitHub-visible content (commit messages, PR titles/bodies, review comments) must be in English.

## Step 4: Create a Pull Request

```bash
gh pr create --title "feat: add user registration" --body "$(cat <<'EOF'
## Summary
- Implement user registration and login
- Support email/password + Cookie session

## Test Plan
- [x] make test
- [x] make lint
EOF
)"
```

Use HEREDOC for the body to avoid quote escaping issues.

## Step 5: Monitor CI

```bash
gh run watch
```

If CI fails:

```bash
gh run view <run-id> --log-failed   # inspect failure
make test                           # reproduce locally
make lint                           # run repo lint checks
```

Fix, then `make ship MSG="fix: ..."` to push the fix.

## Step 6: Merge

Once CI is green:

```bash
gh pr merge --squash
git checkout main && git pull
```

## K8s Verification (When Needed)

If the change affects sandbox orchestration or deployment, verify on a local Kind cluster before merging. Follow `deploy/README.md` for the full workflow:

```bash
make up          # build + deploy to Kind
make test-e2e    # run E2E tests against the cluster
make down        # tear down when done
```

## Quick Reference

Run `make help` for the full command list.
