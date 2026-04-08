# Cursor Cloud Agent — Environment & Workflow Guide

This document is for **Cursor Cloud agents only**. Other environments (local macOS/Linux, GitHub Actions CI) should ignore it.

## Constraints

Cursor Cloud VMs are containers inside Firecracker. **No K8s distribution works** (Kind, k3d/k3s, minikube) because cgroupv2 delegation is incomplete — runc cannot create Pod cgroups. Therefore `make local` and `make test-e2e` are unavailable. See [root-cause details](#why-k8s-fails) at the bottom.

## What you CAN do

| Capability | Command |
|------------|---------|
| Unit + API tests (726+) | `unset TREADSTONE_JWT_SECRET TREADSTONE_DEBUG && make test` |
| Web frontend tests | `cd web && pnpm test` |
| Lint | `make lint` |
| API dev server | `make dev-api` (port 8000, hot reload) |
| Web dev server | `make dev-web` (port 5173, hot reload) |
| DB migrations | `make migrate` |
| OpenAPI / SDK generation | `make gen-openapi`, `make gen-web-types`, `make gen-sdk-python` |
| Auth, Admin, API Key, Docs — all non-K8s API routes | Full read/write via dev server |

## What you CANNOT do

- Sandbox lifecycle (create/start/stop/delete) — requires K8s CRDs
- K8s watch-based metering/sync
- E2E tests (`make test-e2e`) — requires deployed cluster
- Sandbox proxy / browser hand-off

## Testing workflow

```
┌─────────────────────────────────┐
│  Cursor Cloud Agent             │
│  1. Write code + unit tests     │
│  2. make test  (726+ tests)     │
│  3. make lint                   │
│  4. Push PR                     │
└──────────┬──────────────────────┘
           │ PR triggers CI automatically
           ▼
┌─────────────────────────────────┐
│  GitHub Actions CI              │
│  • ci.yml: lint + test + build  │
│  • k8s-e2e.yml: Kind + deploy   │
│    + Hurl E2E (full stack)      │
└──────────┬──────────────────────┘
           │ If E2E fails
           ▼
┌─────────────────────────────────┐
│  Agent reads CI logs, fixes,    │
│  pushes again                   │
└─────────────────────────────────┘
```

### Step 1 — Local verification

Run before every push:

```bash
unset TREADSTONE_JWT_SECRET TREADSTONE_DEBUG
make test          # unit + API tests
make lint          # ruff + eslint
cd web && pnpm test  # frontend tests
```

### Step 2 — Push PR, CI runs automatically

PR creation triggers `ci.yml` (lint + test + build) and `k8s-e2e.yml` (Kind + full-stack E2E). Watch status:

```bash
gh pr checks          # overview
gh run list --branch $(git branch --show-current)  # list runs
```

### Step 3 — Manually trigger E2E (optional)

If you need to run K8s E2E without a PR (e.g. on `workflow_dispatch`):

```bash
# Trigger the K8s E2E workflow on the current branch
gh workflow run "K8s E2E"

# Trigger with a specific Hurl test file
gh workflow run "K8s E2E" -f file=01-auth-flow.hurl
```

### Step 4 — Debug CI failures

```bash
# Find the failed run
gh run list --workflow=k8s-e2e.yml --limit=5

# View full logs
gh run view <run-id> --log-failed

# Or download logs
gh run view <run-id> --log > /tmp/ci-e2e.log
```

Fix the issue locally, run `make test` + `make lint`, push, and CI will re-run.

## Environment setup notes

### Env vars conflict with tests

The Cursor Cloud environment injects `TREADSTONE_JWT_SECRET` (too short, < 32 chars) and `TREADSTONE_DEBUG=true`. These conflict with test fixtures. **Always unset them before running tests:**

```bash
unset TREADSTONE_JWT_SECRET TREADSTONE_DEBUG && make test
```

### `.env` file (for `make dev-api`)

Created from `.env.example`. Key overrides for bare dev mode (no K8s):

```
TREADSTONE_LEADER_ELECTION_ENABLED=false
TREADSTONE_APP_BASE_URL=http://localhost:8000
TREADSTONE_JWT_SECRET=<at least 32 chars>
```

### pnpm esbuild warning

`pnpm install --frozen-lockfile` may warn about ignored esbuild build scripts. This is harmless — vite resolves esbuild through its dependency chain regardless.

---

## Why K8s fails

For reference only. Do not attempt to fix this — it is a Firecracker/kernel limitation.

| Factor | GitHub Actions (`ubuntu-24.04`) | Cursor Cloud VM |
|--------|-------------------------------|-----------------|
| Host PID 1 | `systemd` (real VM) | `pod-daemon` (nested container) |
| cgroupv2 subtree delegation | all controllers | partial (`cpuset cpu pids` only; `+memory`/`+io` → `ENOTSUP`) |
| Root cgroup evacuation | PID 1 movable to `init.scope` | `ENOTSUP` |
| Docker storage driver | native `overlay2` | `fuse-overlayfs` (workaround) |

**Kind** fails: systemd can't reach `multi-user.target`.
**k3s/k3d**: API server starts but Pods stay `ContainerCreating` — runc: `cannot enter cgroupv2 "/sys/fs/cgroup/k8s.io" with domain controllers -- it is in an invalid state`.
