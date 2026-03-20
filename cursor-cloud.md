# Cursor Cloud Agent Instructions

This file contains environment-specific instructions for Cursor Cloud Agents running in Cloud Agent VMs.

## Services overview

Treadstone is a single FastAPI backend service. It requires:
- **Neon PostgreSQL** (external) — set `TREADSTONE_DATABASE_URL` secret for DB-dependent features (auth, sandboxes, migrations). Without it, unit/API tests still pass (they use in-memory SQLite), the dev server starts, and `/health` works, but auth and CRUD endpoints return 500.
- **Kubernetes** — not needed for local dev. `TREADSTONE_DEBUG=true` activates `FakeK8sClient`.

## Running the dev environment

1. `make install` installs all deps via `uv sync` and configures git hooks.
2. Copy `.env.example` to `.env` (already has `TREADSTONE_DEBUG=true`). Set `TREADSTONE_DATABASE_URL` if you have a Neon connection string.
3. `make dev` starts uvicorn on port 8000 with hot reload.
4. The k8s_sync background task will log DB connection errors on startup if no real DB is configured — this is expected and does not prevent the server from serving non-DB endpoints.

## Testing caveats

- `make test` runs unit + API tests (137+) using in-memory SQLite — no real DB needed.
- `make test-all` includes integration tests that require `TREADSTONE_DATABASE_URL` pointing to a real Neon instance.
- API tests override DB session via `app.dependency_overrides` with `sqlite+aiosqlite://`. If you add new API tests needing DB, follow the same pattern in `tests/api/test_auth_api.py`.

## Lint / format

- `make lint` (ruff check + format check), `make format` (auto-fix). See Makefile for details.

## K8s cluster in Cloud Agent VM

Kind does **not** work in Cloud Agent VMs (Firecracker) — systemd and kernel features are missing. Use **k3s** directly instead:

```bash
# Install k3s binary (skip systemd service registration)
curl -sfL https://get.k3s.io | INSTALL_K3S_SKIP_START=true sh -

# Start k3s server-only (no agent — avoids cgroup/overlayfs issues)
sudo k3s server \
  --disable traefik --disable metrics-server \
  --write-kubeconfig-mode 644 --data-dir /tmp/k3s \
  --snapshotter fuse-overlayfs --flannel-backend host-gw \
  --kubelet-arg=cgroups-per-qos=false \
  --kubelet-arg=enforce-node-allocatable="" \
  --disable-agent &>/tmp/k3s-server.log &

# Copy kubeconfig
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

Key caveats:
- **Server-only mode** (`--disable-agent`): K8s API works for CRDs/resources, but no Pods can be scheduled (no nodes). The agent-sandbox controller won't run as a Pod.
- **fuse-overlayfs** is required (kernel doesn't support overlayfs).
- **host-gw** flannel backend is needed (VXLAN not supported by kernel).
- To run Treadstone against the real K8s API, set `TREADSTONE_DEBUG=false` in `.env` and unset the `TREADSTONE_DEBUG` env var if it was exported in the shell.
- Sandbox creation via API works (creates SandboxClaim in K8s), but sandboxes stay in "creating" state without a running controller.
