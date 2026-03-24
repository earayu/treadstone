# Treadstone

**Agent-Native sandbox.** Run code, build projects, deploy environments.

> [!NOTE]
> Treadstone is in early development. The CLI commands in this README reflect
> what works today. Future ergonomic commands are called out explicitly when
> they are still part of the product vision.

## Why Treadstone?

AI agents need isolated environments to execute code, install packages, run
tests, and build software. Existing sandbox solutions are either designed for
human developers to self-host (requiring a Kubernetes cluster and significant
ops work) or locked behind proprietary APIs with no self-deploy option.

Treadstone takes a different approach: **an agent-native sandbox service** that
agents interact with directly via CLI and SDK, while remaining fully open source
and self-hostable.

| | Self-host sandbox platforms | Proprietary sandbox APIs | **Treadstone** |
|---|---|---|---|
| **Audience** | Developers building platforms | Developers integrating SDKs | AI agents operating autonomously |
| **Setup** | Deploy K8s + controllers + CRDs | Sign up for API key | `treadstone run "print('hello')"` |
| **Self-host** | Yes | No | Yes |
| **Managed option** | No | Yes | Yes |
| **Multi-tenant** | Build it yourself | Built-in | Built-in |

## Quick Start

### Install

```bash
pip install git+https://github.com/earayu/treadstone.git
```

### CLI

```bash
# Check that the server is reachable
treadstone system health

# Register and log in
treadstone auth register --email you@example.com --password YourPass123!
treadstone auth login --email you@example.com --password YourPass123!

# Create and save an API key for non-interactive use
treadstone api-keys create --name my-key --save

# Optional: override the server URL explicitly
export TREADSTONE_BASE_URL="http://localhost:8000"

# List available templates
treadstone templates list

# Create a sandbox
treadstone sandboxes create --template aio-sandbox-tiny --name my-sandbox

# List and inspect sandboxes
treadstone sandboxes list
treadstone sandboxes get <sandbox_id>

# Generate a browser hand-off URL for a human
treadstone sandboxes web enable <sandbox_id>

# Create a persistent sandbox with storage
treadstone sandboxes create --template aio-sandbox-large --persist --storage-size 20Gi

# Lifecycle management
treadstone sandboxes stop <sandbox_id>
treadstone sandboxes start <sandbox_id>
treadstone sandboxes delete <sandbox_id>

# Print the built-in AI usage guide
treadstone guide agent
treadstone --skills

# All commands support JSON output for automation
treadstone --json sandboxes list
```

### Python SDK

```python
from treadstone_sdk import Client

client = Client(base_url="http://localhost:8000")

# All API operations are available as typed methods
# See sdk/python/ for the full generated SDK
```

## Authentication Model

Treadstone currently uses two credential types:

- **Session Cookie** authenticates browser-oriented control plane flows. In the
  CLI, `treadstone auth login` saves the session locally for the active base
  URL.
- **API Key** authenticates programmatic access across both the **control plane**
  and **data plane**.

For protected CLI commands, API keys take precedence. If no API key is set, the
CLI falls back to the saved login session for the active base URL.

API keys default to full user access, but can now be narrowed with coarse
scopes:

- `control_plane`: enable or disable account and sandbox management APIs
- `data_plane.mode = all | none | selected`
- `data_plane.sandbox_ids`: restrict data plane access to specific sandboxes

This keeps the default API/CLI/SDK path simple while leaving room for finer
grained scopes in a future release.

## Sandbox Templates

Treadstone ships with five built-in size tiers — all powered by the same
AIO (All-in-One) image with different resource allocations. No ecosystem to
maintain, no marketplace to curate.

| Template | CPU | Memory | Use Case |
|----------|-----|--------|----------|
| `aio-sandbox-tiny` | 0.25 core | 512 Mi | Code execution, script running |
| `aio-sandbox-small` | 0.5 core | 1 Gi | Simple development tasks |
| `aio-sandbox-medium` | 1 core | 2 Gi | General-purpose development |
| `aio-sandbox-large` | 2 cores | 4 Gi | Full-featured + browser automation |
| `aio-sandbox-xlarge` | 4 cores | 8 Gi | Heavy workloads |

Current CLI examples:

```bash
# Lightweight sandbox
treadstone sandboxes create --template aio-sandbox-tiny --name quick-demo

# Persistent development environment
treadstone sandboxes create --template aio-sandbox-large --name dev-box --persist --storage-size 20Gi
```

Future ergonomic goal (not implemented yet):

```bash
treadstone run --template aio-sandbox-tiny "import math; print(math.pi)"
treadstone create --template aio-sandbox-large --persist --storage 20Gi
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  CLI / Python SDK / REST API                         │
├──────────────────────────────────────────────────────┤
│  Platform Service Layer          (Treadstone)        │
│  Auth · API Keys · RBAC · Rate Limiting · Billing    │
├──────────────────────────────────────────────────────┤
│  Orchestration Layer                                 │
│  Kubernetes · agent-sandbox CRD · WarmPool           │
├──────────────────────────────────────────────────────┤
│  Sandbox Runtime Layer                               │
│  Container · gVisor Isolation · Persistent Volumes   │
└──────────────────────────────────────────────────────┘
```

**Platform Service Layer** — Authentication, multi-tenancy, API key management,
rate limiting, and usage metering. This is what turns an open-source sandbox
runtime into a production-ready service.

**Orchestration Layer** — Kubernetes-native scheduling via
[agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRDs with
warm pool pre-provisioning for fast startup.

**Sandbox Runtime Layer** — Isolated container execution with gVisor secure
runtime. Supports both ephemeral (no storage) and persistent (PVC-backed)
sandbox modes.

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), asyncpg |
| Database | [Neon](https://neon.tech) Serverless PostgreSQL |
| Orchestration | Kubernetes, [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRD |
| Isolation | [gVisor](https://gvisor.dev/) (K8s RuntimeClass) |
| Runtime | [agent-infra/sandbox](https://github.com/agent-infra/sandbox) |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| CI/CD | GitHub Actions → GHCR |

## Status

Treadstone is under active development. Here is what works today and what is
coming next.

| Phase | Scope | Status |
|---|---|---|
| **Phase 1** | User auth (JWT, OAuth, API keys), RBAC, invitation system | Done |
| **Phase 2** | Sandbox CRUD, lifecycle management, K8s sync, HTTP proxy, subdomain routing | Done |
| **Phase 3** | CLI, Python SDK, agent-facing developer experience | Done |
| **Phase 4** | Usage metering, billing (Stripe), quotas | Planned |
| **Phase 5** | Managed hosting, production hardening, monitoring | Planned |

Design documents and implementation plans are available in the
[docs/](docs/zh-CN/plans/) directory.

## Development

```bash
make help             # Show all available commands
make dev              # Start local dev server (hot reload)
make test             # Run tests
make lint             # Lint check
make format           # Auto-format
make migrate          # Run database migrations
make migration MSG=x  # Generate a new migration
make build            # Build Docker image
make up               # Spin up local Kind cluster + deploy
make down             # Tear down local environment
```

## License

[Apache License 2.0](LICENSE)
