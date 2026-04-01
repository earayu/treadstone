# Treadstone

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/earayu/treadstone)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Agent-native sandbox platform.** Spin up isolated environments, run code and tools inside them, reach workloads over HTTP/WebSocket (including MCP), and **hand the browser session to a human** when review or takeover matters—all through the same **CLI**, **Python SDK**, and **REST API**.

Open source and self-hostable. Built for **developers** shipping agent workflows and for **automation** that needs stable, machine-readable surfaces (`--json`, OpenAPI, and predictable errors).

---

## Why Treadstone?

Autonomous work needs more than a raw container: **identity**, **API keys**, **multi-tenant lifecycle**, **usage limits**, and a **data plane** that routes traffic into the box without you inventing a new ingress story per project.

Treadstone is a **control plane** for sandboxes plus a **data plane** into what runs inside them—so agents can create environments, drive tooling, and invite humans without pasting long-lived secrets into prompts.

---

## Two ideas: control plane vs data plane

Almost everything maps to one of these:

| | **Control plane** | **Data plane** |
| --- | --- | --- |
| **What** | Accounts, sandboxes, templates, API keys, usage, lifecycle | Traffic **into** the sandbox: browser workspace, HTTP proxy, MCP |
| **How you call it** | `https://api…/v1/…` with a session or API key scoped for management | `urls.proxy` / `urls.mcp` / `urls.web` from **`GET /v1/sandboxes/{id}`**—with an API key on the proxy when required |

You do **not** hand-build `urls.*` strings. They come from **`treadstone sandboxes get <id>`** or the API. See **[Sandbox endpoints](https://treadstone-ai.dev/docs/sandbox-endpoints)** (Web / MCP / Proxy) and **[Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox)** for calling HTTP into a running sandbox.

---

## What you can do

- **Lifecycle** — Create, list, start, stop, and delete sandboxes from templates; optional persistence. See **[Sandbox Lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle)**.
- **Integrate** — Same product surface from **[CLI](https://treadstone-ai.dev/docs/cli-guide)**, **[REST](https://treadstone-ai.dev/docs/rest-api-guide)**, and **[Python SDK](https://treadstone-ai.dev/docs/python-sdk-guide)**.
- **Data plane** — Proxy HTTP/WebSocket to the workload; MCP under the proxy path family; merged runtime routes (shell, file, browser, …) in **[Swagger](https://api.treadstone-ai.dev/docs)** and **[API Reference](https://treadstone-ai.dev/docs/api-reference)**.
- **Browser handoff** — Short-lived links so a person can open the workspace in a browser. See **[Browser Handoff](https://treadstone-ai.dev/docs/browser-handoff)**.
- **Auth & scope** — Sessions, API keys, control-plane vs data-plane access, and optional per-sandbox grants. See **[API Keys & Auth](https://treadstone-ai.dev/docs/api-keys-auth)**.
- **Plans & limits** — Templates, concurrency, compute, storage. See **[Usage & Limits](https://treadstone-ai.dev/docs/usage-limits)**.
- **Errors** — Stable JSON envelope and codes. See **[Error Reference](https://treadstone-ai.dev/docs/error-reference)**.

---

## Quick start

### Install the CLI

```bash
curl -fsSL https://treadstone-ai.dev/install.sh | sh
```

Windows (PowerShell): `irm https://treadstone-ai.dev/install.ps1 | iex` — or `pip install treadstone-cli`.

### Human workflow

```bash
# Optional: self-hosted or local Kind (see deploy/README.md)
export TREADSTONE_BASE_URL="http://api.localhost"

treadstone system health
treadstone auth login
treadstone api-keys create --name local --save
treadstone sandboxes create --template aio-sandbox-tiny --name demo
treadstone sandboxes web enable <sandbox_id>
```

Use **`sandbox_id`** (not `name`) for follow-up calls. Read **`urls.proxy`**, **`urls.web`**, and handoff fields from **`treadstone sandboxes get`**—do not guess hostnames.

### Agent workflow

Prefer **`--json`** and structured output.

```bash
treadstone --json system health
treadstone --json api-keys create --name automation --save
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes get <sandbox_id>
treadstone guide agent
treadstone --skills
```

Full step-by-step: **[Quickstart](https://treadstone-ai.dev/docs/quickstart)**.

---

## Documentation

Hosted documentation on **[treadstone-ai.dev](https://treadstone-ai.dev/)** is the source of truth for contracts, limits, and URLs. **[Documentation Sitemap](https://treadstone-ai.dev/docs/sitemap)** lists every page.

### Get Started

| Topic | Link |
| --- | --- |
| Overview (control vs data plane) | [Overview](https://treadstone-ai.dev/docs/index) |
| Install, sign in, first sandbox | [Quickstart](https://treadstone-ai.dev/docs/quickstart) |
| **`urls.web`**, **`urls.mcp`**, **`urls.proxy`** | [Sandbox endpoints](https://treadstone-ai.dev/docs/sandbox-endpoints) |

### Core Workflows

| Topic | Link |
| --- | --- |
| Create, start, stop, delete | [Sandbox Lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle) |
| Human browser entry & links | [Browser Handoff](https://treadstone-ai.dev/docs/browser-handoff) |
| Sessions, API keys, OAuth, scopes | [API Keys & Auth](https://treadstone-ai.dev/docs/api-keys-auth) |
| **`curl` proxy, MCP pointer, Swagger** | [Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox) |
| Plans, compute, storage, concurrency | [Usage & Limits](https://treadstone-ai.dev/docs/usage-limits) |

### Integrate

| Topic | Link |
| --- | --- |
| CLI flags, JSON, config, skills | [CLI Guide](https://treadstone-ai.dev/docs/cli-guide) |
| REST shape, headers, errors, proxy | [REST API Guide](https://treadstone-ai.dev/docs/rest-api-guide) |
| MCP over the data plane | [MCP in sandbox](https://treadstone-ai.dev/docs/mcp-sandbox) |
| `AuthenticatedClient`, codegen, async | [Python SDK Guide](https://treadstone-ai.dev/docs/python-sdk-guide) |

### Reference

| Topic | Link |
| --- | --- |
| Control-plane routes + proxy summary | [API Reference](https://treadstone-ai.dev/docs/api-reference) |
| CLI surface | [CLI Reference](https://treadstone-ai.dev/docs/cli-reference) |
| SDK modules and models | [Python SDK Reference](https://treadstone-ai.dev/docs/python-sdk-reference) |
| Error envelope & codes | [Error Reference](https://treadstone-ai.dev/docs/error-reference) |

**Machine-readable API:** [`/openapi.json`](https://treadstone-ai.dev/openapi.json) (hosted spec includes merged sandbox proxy paths) · **Interactive:** [api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs)

---

## MCP (Model Context Protocol)

If the workload exposes MCP, clients connect using **`urls.mcp`** from the sandbox response (same path family as **`urls.proxy`**). Use **`Authorization: Bearer <api_key>`** on the data plane; **not** a Console session cookie. HTTP/SSE and WebSocket are supported.

Details: **[MCP in sandbox](https://treadstone-ai.dev/docs/mcp-sandbox)** · Self-hosted DNS and ingress: **[deploy/README.md](deploy/README.md)**

---

## Python SDK

```bash
pip install treadstone-sdk
```

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="sk_your_api_key")
templates = sandbox_templates_list_sandbox_templates.sync(client=client)
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template=templates.items[0].name, name="demo"),
)
print(sandbox.id)
```

**[Python SDK Guide](https://treadstone-ai.dev/docs/python-sdk-guide)**

---

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

Persistent storage presets include **`5Gi`**, **`10Gi`**, and **`20Gi`**.

---

## Architecture

- **Platform service layer** — Authentication, API keys, RBAC, rate limits, usage metering, plan limits, multi-tenancy
- **Orchestration layer** — Kubernetes and [agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) CRDs (including warm pool support)
- **Sandbox runtime layer** — Isolated workloads with [gVisor](https://gvisor.dev/) and optional persistent volumes

---

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

---

## Project status

**Shipped today**

- User authentication, API keys, RBAC, and invitations
- Sandbox CRUD and lifecycle; Kubernetes sync
- HTTP/WebSocket data-plane proxy (including MCP) and browser hand-off
- CLI and Python SDK for control-plane automation
- Usage metering, plans, and limits (`GET /v1/usage` and related); see **[Usage & Limits](https://treadstone-ai.dev/docs/usage-limits)**

**On the roadmap**

- Managed hosting as a first-class offering
- Deeper production hardening, billing integrations, and observability (iterative)

Paid checkout, invoicing, and similar payment-closed-loop features are **not** represented as shipped; self-serve billing may arrive later.

**Chinese documentation** (module-based, code-first): [docs/zh-CN/README.md](docs/zh-CN/README.md)

---

## Development

```bash
make help             # All commands
make install          # Python + web deps and git hooks
make dev-api          # API dev server (hot reload)
make dev-web          # Web dev server
make test             # Tests
make lint             # Python + web lint
make format-py        # Format Python
make migrate          # Apply DB migrations
make migration MSG=x  # New Alembic migration
make image-api        # Build API image
make image-web        # Build web image
make local            # local Kind cluster + deploy (see deploy/README.md for kubectl context)
make destroy-local    # Tear down local env
```

Local Kubernetes and smoke tests: **[deploy/README.md](deploy/README.md)**

### Release

Cut a release in **GitHub Actions**: **Actions** → **Release** → **Run workflow**, and enter **version** as `x.y.z` only (no `v` prefix — same as Docker image tags and PyPI). The workflow bumps package versions, updates prod Helm image tags in `deploy/`, commits to `main`, pushes tag `vx.y.z`, and publishes images and GitHub Release assets. Do not use `make bump` or `make release` (deprecated).

---

## Community

- [Discord](https://discord.gg/ygSP9tT5RB)
- [X (Twitter)](https://x.com/treadstone_ai)

---

## License

[Apache License 2.0](LICENSE)
