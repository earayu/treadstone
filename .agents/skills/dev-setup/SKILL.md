---
name: dev-setup
description: First-time Treadstone local development environment setup. Run once after cloning the repo and before starting any development. Covers system dependency installation, Python environment, Neon database connection, migrations, and environment verification. Use this skill when the user/agent just entered the project, needs to rebuild the environment, or encounters setup-related issues like missing dependencies, broken .env, or failed migrations.
---

# First-Time Dev Environment Setup

Run this once. After completion, switch to the `dev-lifecycle` skill for daily development.

## 1. System Dependencies

Verify these tools are installed:

```bash
python3 --version        # 3.12+
uv --version             # Python package manager
gh --version             # GitHub CLI (optional, for PR/issue ops)
docker --version         # Container builds + Kind cluster
kind --version           # Local K8s cluster (sandbox dev only)
kubectl version --client # K8s CLI
helm version --short     # Helm chart deployment
hurl --version           # E2E testing (HTTP request runner)
```

Install missing tools (macOS):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
brew install kind kubectl helm hurl
```

## 2. Install Python Dependencies

```bash
make install
```

This runs `uv sync` (creates `.venv`, installs all deps) and configures git hooks.

## 3. Configure Database (Neon)

The project uses [Neon](https://neon.tech) Serverless PostgreSQL — no local Postgres needed.

Get the connection string from https://console.neon.tech, then:

```bash
cp .env.example .env
```

Edit `.env` and set the connection string in asyncpg format:

```
TREADSTONE_DATABASE_URL=postgresql+asyncpg://neondb_owner:xxx@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
TREADSTONE_DEBUG=true
```

The URL scheme must be `postgresql+asyncpg://` (not `postgresql://`). Keep `?sslmode=require`.

## 4. Apply Database Migrations

```bash
make migrate
```

Expected: `INFO [alembic.runtime.migration] Context impl PostgresqlImpl.` with migration details listed.

## 5. Verify Environment

```bash
make test
```

Expected: all tests pass (integration tests are excluded by default). If tests pass, the environment is ready.

## 6. Local K8s Cluster (Sandbox Development)

For sandbox-related features that require a real Kubernetes cluster, follow `deploy/README.md` — it covers Kind cluster creation, image building, Helm deployment, and smoke testing end-to-end.

Quick start:

```bash
make up   # One-command: Kind cluster + build + deploy
```

Pure API development (`make dev`) does not require a K8s cluster.

---

## Troubleshooting

**`uv sync` fails:**
- Confirm Python 3.12+: `python3 --version`
- Try: `uv python install 3.12`

**Database connection fails (`could not connect`):**
- Check the connection string in `.env`
- Confirm the URL uses `postgresql+asyncpg://` not `postgresql://`
- Neon free-tier projects auto-suspend; first connection may be slow (~1s cold start)

**`alembic upgrade head` reports `authentication failed`:**
- Confirm `.env` exists in the project root
- URL-encode special characters in the password
