---
name: dev-lifecycle
description: Treadstone development lifecycle — feature branches, TDD, ship, PR, CI, merge, version bump, tagged release, and optional production deploy. Use for any shippable code change, GitHub flow, or release. Includes agreed “codeword” paths (合并代码 / 发版本 / 发生产). Source of truth for agents executing ship, bump, release, merge, or deploy-all.
---

# Development Lifecycle

**This file is the source of truth** for how agents run Git work, pull requests, CI, version bumps, releases, and production deployment. Follow it end-to-end; do not duplicate these procedures elsewhere except with a pointer here.

Never push directly to `main`. All changes land via Pull Requests, including work done by AI agents.

All GitHub-visible text must be in English: commits, PR titles/bodies, review notes, release notes.

---

## Agreed trigger phrases (codewords)

These are shorthand agreements with the project owner. When the user uses one of them, follow the matching path **fully** (including waiting for the right workflows).

### 1. 合并代码 — “merge the code”

**Intent:** Land the current work on `main` with automation.

**Do:**

1. Ensure work is on a **feature branch** (not `main`), pushed, and tested as needed (`make test`, `make lint`).
2. Open a PR with `gh pr create` if one does not exist (HEREDOC body: Summary + Test Plan).
3. Watch CI until it succeeds: `gh run watch` (or inspect failures with `gh run view <id> --log-failed`).
4. When CI is green, merge: `gh pr merge --squash`.
5. Update local `main`: `git checkout main && git pull`.

Do not stop after opening the PR; continue until **merge is complete** unless the user aborts.

### 2. 发版本 — “cut a release”

**Intent:** Publish a **patch** release and wait until the **Release** GitHub Actions workflow finishes successfully.

**Default:** Start from an up-to-date `main`, bump **one patch** version (e.g. `0.7.12` → `0.7.13`). Use another semver only if the user specifies it.

**Do:**

1. Sync: `git fetch origin && git checkout main && git pull`.
2. Read the current version from `pyproject.toml` (root `version = "x.y.z"`) and compute the next **patch** `V=x.y.(z+1)` unless the user gave an explicit `V`.
3. Create a bump branch: `git checkout -b chore/release-x.y.z` (use the new version in the name).
4. Run **`make bump V=x.y.z`** (must not be on `main`). This updates version files, commits, and pushes the branch.
5. Open a PR for the bump branch, wait for CI, then **`gh pr merge --squash`**.
6. On **updated `main`**: `git checkout main && git pull`.
7. Run **`make release V=x.y.z`** (only on `main`). This creates and pushes tag `vx.y.z` and triggers [`.github/workflows/release.yml`](../../../.github/workflows/release.yml).
8. Wait until the **Release** workflow completes **successfully** (`gh run watch` or equivalent). Do not treat the release as done while the workflow is running or failed.

Do not hand-craft `git tag`, `git push origin v…`, or `gh release create` unless fixing a broken release (see `AGENTS.md` guardrails).

### 3. 发生产 — “deploy to production”

**Intent:** After a successful version release, wait for the **prod image bump** on `main`, then deploy to the production cluster.

**Prerequisite:** A **发版本** completed through a successful **Release** workflow (tag pushed).

**Do:**

1. Wait for the **Update Prod Image** workflow to finish successfully after that Release. It runs when the Release workflow completes ([`.github/workflows/update-prod-image.yml`](../../../.github/workflows/update-prod-image.yml)) and commits the new image tag to `deploy/treadstone/values-prod.yaml` on `main`.
2. On your machine, sync `main`: `git checkout main && git pull` so you have the committed prod image tag and any other changes.
3. Deploy production. The Makefile matches `deploy/*/values-<env>.yaml`; use **`ENV=prod`** (lowercase) so it resolves to `values-prod.yaml`. If the owner says **`ENV=PROD`**, treat it as the same intent and run `make deploy-all ENV=prod`.

   ```bash
   make deploy-all ENV=prod
   ```

Do not run `make deploy-all` until **Update Prod Image** has succeeded (otherwise the cluster may not track the intended image tag on `main`).

---

## The everyday development loop

Feature work (no version bump):

```
branch → TDD → ship → PR → CI → merge
```

---

## Step 1: Create a feature branch

```bash
git checkout main && git pull
git checkout -b feat/descriptive-name
```

Use prefixes: `feat/`, `fix/`, `chore/`, `refactor/`, `docs/`, `test/`.

---

## Step 2: TDD cycle

Keep iterations small. For docs-only changes, do not invent fake tests; validate paths and commands against the repo and run `git diff --check`.

1. Add a failing test under `tests/unit/`, `tests/api/`, or `tests/integration/` (see `AGENTS.md` → Testing).
2. `make test` — confirm red.
3. Implement the minimum to pass.
4. `make test` — confirm green.
5. Refactor if needed; re-run `make test`.

### Docs-only changes

For `README.md`, `AGENTS.md`, `.agents/skills/*/SKILL.md`, or similar:

- Still use a branch and PR.
- Prefer `docs:` commits.
- Run `git diff --check` before shipping.

---

## Step 3: Ship to the feature branch

```bash
make ship MSG="feat: add user registration endpoint"
```

Runs `git add -A`, `git commit`, `git push` on the current branch. **Never** run from `main` (`make` will error).

Commit messages: Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `docs:`). Small, one logical unit per commit.

---

## Step 4: Open a Pull Request

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

Use a HEREDOC for `--body` to avoid quoting bugs.

### Large OpenAPI / SDK diffs

When `make gen-sdk-python` or `make gen-web-types` produces a large diff:

1. **Preferred:** Two commits — (1) hand-written code + migrations + optional `web/src/api/schema.d.ts` from `make gen-web-types`; (2) `chore: regenerate Python SDK from OpenAPI` touching **`sdk/python/`** only.
2. **Single commit:** State in the PR body that `sdk/python/**` and `web/src/api/schema.d.ts` are generated only.

See `AGENTS.md` → OpenAPI / SDK Generation.

---

## Step 5: Monitor CI

```bash
gh run watch
```

On failure:

```bash
gh run view <run-id> --log-failed
make test
make lint
```

Fix, then `make ship MSG="fix: ..."` and push.

---

## Step 6: Merge

When CI is green:

```bash
gh pr merge --squash
git checkout main && git pull
```

For **合并代码**, this merge step is mandatory unless the user says otherwise.

---

## K8s verification (when the change affects orchestration or deploy)

Before merging risky work, validate on Kind per `deploy/README.md`:

```bash
kubectl config use-context kind-treadstone
make local
make test-e2e
make destroy-local
```

---

## Automation reference (read-only context)

- **CI** on PRs: lint, tests, OpenAPI checks, etc. Failures block merge.
- **Release** (`.github/workflows/release.yml`): runs on tag push `v*`.
- **Update Prod Image** (`.github/workflows/update-prod-image.yml`): after a successful Release run, updates `deploy/treadstone/values-prod.yaml` on `main`.

Operational steps for agents live in this skill, not in workflow YAML.

---

## Quick reference

| Goal | Command / pointer |
|------|-------------------|
| Commit + push branch | `make ship MSG="fix: ..."` |
| Bump version (on bump branch) | `make bump V=x.y.z` |
| Tag release (on `main` after bump merge) | `make release V=x.y.z` |
| Prod deploy | `make prod` or `make deploy-all ENV=prod` (set `TREADSTONE_PROD_CONTEXT` and `kubectl` context; see `deploy/README.md`) |
| Full Makefile | `make help` |
