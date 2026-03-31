# Treadstone

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/earayu/treadstone)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Agent-native sandbox infrastructure.** Create sandboxes, manage lifecycle, use the HTTP/WebSocket data plane (including MCP), and hand browser sessions to humans when the workflow needs it—all from a consistent CLI, Python SDK, and REST API.

Open source and self-hostable. Built for two readers at once:

- **Developers** who want a sandbox control plane without building the whole platform themselves
- **AI agents** that need predictable, machine-readable interfaces they can run autonomously

## Why Treadstone?

Autonomous software work needs more than a raw container: authentication, API keys, multi-tenant lifecycle, structured output, optional persistence, and **browser hand-off** when a human must step in.

Treadstone packages that into an **agent-native control plane** so you do not have to assemble auth, routing, and Kubernetes wiring from scratch for every project.

## Quick start

### Install the CLI

Use the release installer (checksums when available) or PyPI:

```bash
curl -fsSL https://treadstone-ai.dev/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://treadstone-ai.dev/install.ps1 | iex
```

Alternative:

```bash
pip install treadstone-cli
```

### Human workflow

```bash
# Optional: point the CLI at your own deployment (after make up / make deploy-all ENV=local, API Ingress is http://api.localhost — see deploy/README.md)
export TREADSTONE_BASE_URL="http://api.localhost"

treadstone system health
treadstone auth register
treadstone auth login
treadstone api-keys create --name local --save
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name demo
treadstone sandboxes list
treadstone sandboxes web enable <sandbox_id>
```

The command returns a browser link. Opening it shows a live view into the sandbox—the in-sandbox browser, editor, terminal, and file tree:

![Sandbox browser handoff](docs/assets/image/sandbox.png)

### Agent workflow

Prefer `--json` and capture IDs from command output.

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

Treat `name` as a human-readable label only. Follow-up operations use `sandbox_id`. Read `urls.proxy`, `web_url`, and `open_link` from platform output—do not construct URLs from the sandbox name.

## Documentation

Hosted docs on **[treadstone-ai.dev](https://treadstone-ai.dev/)** are the source of truth for contracts, commands, and limits. Start here:

| Topic | Link |
| --- | --- |
| Overview | [Overview](https://treadstone-ai.dev/docs/index) |
| Install & CLI behavior | [CLI Guide](https://treadstone-ai.dev/docs/cli-guide) |
| Sessions, API keys, OAuth, scopes | [API Keys & Auth](https://treadstone-ai.dev/docs/api-keys-auth) |
| REST shape & control vs data plane | [REST API Guide](https://treadstone-ai.dev/docs/rest-api-guide) |
| Create, stop, start, delete sandboxes | [Sandbox Lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle) |
| Human browser entry & links | [Browser Handoff](https://treadstone-ai.dev/docs/browser-handoff) |
| Plans, compute, storage, concurrency | [Usage & Limits](https://treadstone-ai.dev/docs/usage-limits) |
| Stable error envelope & codes | [Error Reference](https://treadstone-ai.dev/docs/error-reference) |
| Full doc index | [Documentation Sitemap](https://treadstone-ai.dev/docs/sitemap) |

**Machine-readable API:** [OpenAPI JSON](https://treadstone-ai.dev/openapi.json) · **Interactive docs (Swagger):** [api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs)

## What you get

- **Three interfaces, one contract**: CLI, [Python SDK](https://treadstone-ai.dev/docs/python-sdk-guide), and REST API
- **Agent-oriented UX**: `--json`, `treadstone guide agent`, and `treadstone --skills`
- **Sandbox lifecycle**: create, inspect, start, stop, delete; ephemeral or persistent storage
- **Data-plane proxy**: HTTP and WebSocket to workloads inside the sandbox (including MCP paths)
- **Browser hand-off**: mint links for humans without embedding long-lived credentials in agent code
- **Identity & scope**: sessions, API keys, RBAC, and per-sandbox grants
- **Usage & plan limits**: compute and storage accounting, remaining quota, and enforcement—see [Usage & Limits](https://treadstone-ai.dev/docs/usage-limits)
- **Self-hosting**: deploy your own stack; see [deploy/README.md](deploy/README.md)

## MCP (Model Context Protocol)

If the sandbox runs an MCP server (for example on `/mcp`), expose it through the **data plane** using **`{urls.proxy}/mcp`** and your API key (`Authorization: Bearer sk-…`). Read **`urls.proxy`** from `GET /v1/sandboxes/{id}`—do not hand-build hostnames. HTTP/SSE and WebSocket are supported.

Details: [MCP in sandbox](https://treadstone-ai.dev/docs/mcp-sandbox) · Proxy contract: [API Reference](https://treadstone-ai.dev/docs/api-reference) · Self-hosted DNS: [deploy/README.md](deploy/README.md)

## Python SDK

```bash
pip install treadstone-sdk
```

Minimal example (use `sandbox.id` for follow-up calls):

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(base_url="http://api.localhost", token="sk_your_api_key")
templates = sandbox_templates_list_sandbox_templates.sync(client=client)
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template=templates.items[0].name, name="demo"),
)
print(sandbox.id)
```

Full guide: [Python SDK Guide](https://treadstone-ai.dev/docs/python-sdk-guide)

## Built-in templates

Five tiers share the same AIO sandbox image.

| Template | CPU | Memory | Use case |
| --- | --- | --- | --- |
| `aio-sandbox-tiny` | 0.25 core | 512 Mi | Scripts, lightweight tasks |
| `aio-sandbox-small` | 0.5 core | 1 Gi | Simple development |
| `aio-sandbox-medium` | 1 core | 2 Gi | General development |
| `aio-sandbox-large` | 2 cores | 4 Gi | Full dev and browser automation |
| `aio-sandbox-xlarge` | 4 cores | 8 Gi | Heavy workloads |

```bash
treadstone sandboxes create --template aio-sandbox-tiny --name quick-demo
treadstone sandboxes create --template aio-sandbox-large --name dev-box --persist --storage-size 5Gi
```

Persistent storage presets: `5Gi`, `10Gi`, and `20Gi`.

## Architecture

Three layers:

- **Platform service layer**: authentication, API keys, RBAC, rate limits, usage metering, plan limits, and multi-tenancy
- **Orchestration layer**: Kubernetes and [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRDs (including warm pool support)
- **Sandbox runtime layer**: isolated containers with [gVisor](https://gvisor.dev/) and optional persistent volumes

## Tech stack

| Component | Technology |
| --- | --- |
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), asyncpg |
| Database | [Neon](https://neon.tech) Serverless PostgreSQL |
| Orchestration | Kubernetes, [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRD |
| Isolation | [gVisor](https://gvisor.dev/) |
| Runtime | [agent-infra/sandbox](https://github.com/agent-infra/sandbox) |
| Package manager | [uv](https://github.com/astral-sh/uv) |
| CI/CD | GitHub Actions → GHCR |

## Project status

**Shipped today**

- User authentication, API keys, RBAC, and invitations
- Sandbox CRUD and lifecycle; Kubernetes sync
- HTTP/WebSocket data-plane proxy (including MCP) and browser hand-off
- CLI and Python SDK for control-plane automation
- Usage metering, user plans, and plan limits (`GET /v1/usage` and related endpoints); see [Usage & Limits](https://treadstone-ai.dev/docs/usage-limits)

**On the roadmap**

- Managed hosting as a first-class offering
- Deeper production hardening, billing integrations, and observability (iterative)

Paid checkout, invoicing, and similar payment-closed-loop features are **not** represented as shipped; self-serve billing may arrive later.

**Chinese documentation** (module-based, code-first): [docs/zh-CN/README.md](docs/zh-CN/README.md)

## Development

```bash
make help             # Show all available commands
make install          # Install Python/web dependencies and git hooks
make dev-api          # Start local API dev server (hot reload)
make dev-web          # Start local web dev server
make test             # Run tests
make lint             # Run Python + web lint checks
make format-py        # Auto-format Python code
make migrate          # Run database migrations
make migration MSG=x  # Generate a new migration
make image-api        # Build API Docker image
make image-web        # Build frontend Docker image
make up               # Spin up local Kind cluster + deploy
make down             # Tear down local environment
```

Local Kubernetes and smoke tests: [deploy/README.md](deploy/README.md)

## Community

- [Discord](https://discord.gg/ygSP9tT5RB)
- [X (Twitter)](https://x.com/treadstone_ai)

## License

[Apache License 2.0](LICENSE)
