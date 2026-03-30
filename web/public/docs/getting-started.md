# Overview & Quickstart

**Treadstone** is an agent-native sandbox platform for AI agents. Run code, install dependencies, execute tests, build software, and hand off a browser session from isolated environments.

Open source and self-hostable. Built for two readers at once:

- **Developers** who want a sandbox control plane without building the whole platform themselves
- **AI agents** that need a predictable CLI, SDK, and API they can operate autonomously

> **Note:** Treadstone is in early development. The commands below reflect what works today.

## Why Treadstone?

Autonomous software work needs more than a raw container.

Agents also need authentication, API keys, multi-tenant sandbox lifecycle management, machine-readable output, browser hand-off for humans, and persistent storage when work needs to survive restarts.

Treadstone packages that into an **agent-native sandbox service** instead of making every team assemble it from scratch on top of Kubernetes.

## Install the CLI

Use the release installer script. It downloads the right binary for your platform and verifies checksums when available.

**macOS / Linux:**

```bash
curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh
```

**Windows PowerShell:**

```powershell
irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex
```

**Alternative (pip):**

```bash
pip install treadstone-cli
```

## Quickstart: Human Workflow

```bash
# Optional: point the CLI at your own deployment
export TREADSTONE_BASE_URL="http://localhost"

treadstone system health
treadstone auth register
treadstone auth login
treadstone api-keys create --name local --save
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name demo
treadstone sandboxes list
treadstone sandboxes web enable <sandbox_id>
```

## Quickstart: Agent Workflow

For automation, prefer JSON output and capture returned IDs from command output.

```bash
treadstone --json system health
treadstone auth register --email agent@example.com --password YourPass123!
treadstone auth login --email agent@example.com --password YourPass123!
treadstone --json api-keys create --name automation --save

treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes get <sandbox_id>
treadstone --json sandboxes web enable <sandbox_id>

treadstone guide agent
treadstone --skills
```

> Use `name` as a human-readable label only. Follow-up operations use `sandbox_id`, and browser URLs should be read from command output instead of constructed from the sandbox name.

## Built-in Templates

Treadstone ships with five built-in size tiers powered by the same AIO sandbox image.

| Template | CPU | Memory | Use Case |
|---|---|---|---|
| `aio-sandbox-tiny` | 0.25 core | 512 Mi | Code execution, scripts, lightweight tasks |
| `aio-sandbox-small` | 0.5 core | 1 Gi | Simple development tasks |
| `aio-sandbox-medium` | 1 core | 2 Gi | General-purpose development |
| `aio-sandbox-large` | 2 cores | 4 Gi | Full-featured development and browser automation |
| `aio-sandbox-xlarge` | 4 cores | 8 Gi | Heavy workloads |

```bash
# Lightweight sandbox
treadstone sandboxes create --template aio-sandbox-tiny --name quick-demo

# Persistent development environment
treadstone sandboxes create --template aio-sandbox-large --name dev-box --persist --storage-size 5Gi
```

## What Treadstone Gives You

- **Agent-ready interfaces**: CLI, Python SDK, and REST API
- **Machine-readable workflows**: `--json` output and a built-in agent guide
- **Sandbox lifecycle management**: create, inspect, start, stop, delete
- **Human hand-off**: generate browser entry links for live sandboxes
- **Flexible execution modes**: ephemeral or persistent sandboxes
- **Production control plane**: auth, API keys, RBAC, rate limiting, and multi-tenancy
- **Open deployment model**: self-host today, managed path planned

## Architecture

Treadstone is organized as three layers:

- **Platform service layer**: authentication, API keys, RBAC, rate limiting, billing hooks, and multi-tenancy
- **Orchestration layer**: Kubernetes plus agent-sandbox CRDs and warm pool support
- **Sandbox runtime layer**: isolated containers with gVisor and optional persistent volumes

| Component | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), asyncpg |
| Database | Neon Serverless PostgreSQL |
| Orchestration | Kubernetes, agent-sandbox CRD |
| Isolation | gVisor |
| Package manager | uv |
| CI/CD | GitHub Actions → GHCR |
