# Treadstone

**Agent-native sandbox platform for AI agents.** Run code, install dependencies, execute tests, build software, and hand off a browser session from isolated environments.

Open source and self-hostable. Built for two readers at once:

- **Developers** who want a sandbox control plane without building the whole platform themselves
- **AI agents** that need a predictable CLI, SDK, and API they can operate autonomously

> [!NOTE]
> Treadstone is in early development. The commands below reflect what works today.

## Why Treadstone?

Autonomous software work needs more than a raw container.

Agents also need authentication, API keys, multi-tenant sandbox lifecycle management, machine-readable output, browser hand-off for humans, and persistent storage when work needs to survive restarts.

Treadstone packages that into an **agent-native sandbox service** instead of making every team assemble it from scratch on top of Kubernetes.

## Quick Start

### Install the CLI

Use the release installer script. It downloads the right binary for your platform and verifies checksums when available.

```bash
curl -fsSL https://github.com/earayu/treadstone/releases/latest/download/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex
```

Alternative:

```bash
pip install treadstone-cli
```

### Human Workflow

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

### Agent Workflow

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

Treat `name` as a human-readable label only. Follow-up operations use `sandbox_id`, and browser URLs should be read from command output instead of constructed from the sandbox name.

## What Treadstone Gives You

- **Agent-ready interfaces**: CLI, Python SDK, and REST API
- **Machine-readable workflows**: `--json` output and a built-in agent guide
- **Sandbox lifecycle management**: create, inspect, start, stop, delete
- **Human hand-off**: generate browser entry links for live sandboxes
- **Flexible execution modes**: ephemeral or persistent sandboxes
- **Production control plane**: auth, API keys, RBAC, rate limiting, and multi-tenancy
- **Open deployment model**: self-host today, managed path planned

## Python SDK

Install:

```bash
pip install treadstone-sdk
```

Example:

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(
    base_url="http://localhost",
    token="sk_your_api_key",
)

templates = sandbox_templates_list_sandbox_templates.sync(client=client)

sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template=templates.items[0].name, name="demo"),
)

print(sandbox.id)
```

Use the SDK when you want typed API access from Python. As with the CLI, use `sandbox.id` for follow-up operations.

## Built-in Templates

Treadstone ships with five built-in size tiers powered by the same AIO sandbox image.

| Template | CPU | Memory | Use Case |
|---|---|---|---|
| `aio-sandbox-tiny` | 0.25 core | 512 Mi | Code execution, scripts, lightweight tasks |
| `aio-sandbox-small` | 0.5 core | 1 Gi | Simple development tasks |
| `aio-sandbox-medium` | 1 core | 2 Gi | General-purpose development |
| `aio-sandbox-large` | 2 cores | 4 Gi | Full-featured development and browser automation |
| `aio-sandbox-xlarge` | 4 cores | 8 Gi | Heavy workloads |

Examples:

```bash
# Lightweight sandbox
treadstone sandboxes create --template aio-sandbox-tiny --name quick-demo

# Persistent development environment
treadstone sandboxes create --template aio-sandbox-large --name dev-box --persist --storage-size 5Gi
```

Persistent sandbox storage uses preset workspace tiers today: `5Gi`, `10Gi`, and `20Gi`.

## Architecture

Treadstone is organized as three layers:

- **Platform service layer**: authentication, API keys, RBAC, rate limiting, billing hooks, and multi-tenancy
- **Orchestration layer**: Kubernetes plus [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRDs and warm pool support
- **Sandbox runtime layer**: isolated containers with [gVisor](https://gvisor.dev/) and optional persistent volumes

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), asyncpg |
| Database | [Neon](https://neon.tech) Serverless PostgreSQL |
| Orchestration | Kubernetes, [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRD |
| Isolation | [gVisor](https://gvisor.dev/) |
| Runtime | [agent-infra/sandbox](https://github.com/agent-infra/sandbox) |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| CI/CD | GitHub Actions -> GHCR |

## Status

What works today:

- User auth, API keys, RBAC, and invitations
- Sandbox CRUD and lifecycle management
- Kubernetes sync, HTTP proxy, and browser hand-off flow
- CLI and Python SDK for agent-facing usage

What is planned next:

- Usage metering and billing
- Managed hosting
- More production hardening and monitoring

Design documents and implementation plans are available in [docs/zh-CN/plans/](docs/zh-CN/plans/).

## Development

```bash
make help             # Show all available commands
make dev              # Start local dev server (hot reload)
make test             # Run tests
make lint             # Lint check
make format           # Auto-format
make migrate          # Run database migrations
make migration MSG=x  # Generate a new migration
make image            # Build backend Docker image
make image-web        # Build frontend Docker image
make up               # Spin up local Kind cluster + deploy
make down             # Tear down local environment
```

For local Kubernetes deployment and smoke testing, see [deploy/README.md](deploy/README.md).

## License

[Apache License 2.0](LICENSE)
