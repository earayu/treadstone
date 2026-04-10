# Treadstone

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/earayu/treadstone)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Treadstone is an agent-native sandbox platform for longer-running AI work.** You can run agents inside isolated sandboxes, or treat sandboxes as tools that agents call on demand. Each sandbox is built around an **all-in-one runtime**: code execution, shell, file system, browser-facing surfaces, MCP, and long-running state.

Treadstone is open source, self-hostable, and built on Kubernetes.

- GitHub: [github.com/earayu/treadstone](https://github.com/earayu/treadstone)
- Demo: [app.treadstone-ai.dev](https://app.treadstone-ai.dev/)
- Docs: [treadstone-ai.dev/docs](https://treadstone-ai.dev/docs)
- API docs: [api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs)

## Why Treadstone

Most agents work well for short, stateless tasks. They break down when the job needs real runtime infrastructure: files, browser interaction, long-lived processes, resumable state, or a way for humans to step in without rebuilding the whole environment around the model.

Treadstone treats the sandbox itself as a first-class primitive. The platform gives you the lifecycle, auth, routing, and usage boundaries around the sandbox, while still exposing the runtime inside it in a way agents can actually use.

## Two ways to use it

### 1. Run the agent inside the sandbox

Use Treadstone when the agent itself should live in the isolated environment and keep working there over time.

### 2. Use the sandbox as a tool

Use Treadstone when your agent runs elsewhere, but needs an isolated environment it can create, inspect, and drive on demand.

In practice, that means an agent can:

- create and manage sandboxes over the **CLI**, **REST API**, or **Python SDK**
- operate what is running inside them through **shell**, **file**, **browser**, **HTTP/WebSocket**, and **MCP**
- hand the same browser session to a human when review or takeover matters

## What one sandbox gives you

Every built-in AIO sandbox is designed as an all-in-one agent environment:

- code execution and shell commands
- file system read/write/download flows
- browser automation and browser handoff
- MCP access through `urls.mcp`
- HTTP/WebSocket access through `urls.proxy`
- long-running processes with optional persistent storage
- cold snapshot support for persistent sandboxes

## Control plane vs data plane

Treadstone has two surfaces:

| Surface | What it is for | Typical entrypoints |
| --- | --- | --- |
| Control plane | Accounts, auth, API keys, sandbox lifecycle, templates, usage, browser handoff | CLI, REST API, Python SDK |
| Data plane | Traffic into a running sandbox: shell, file, browser, MCP, and your own HTTP services | `urls.proxy`, `urls.mcp`, `urls.web` from `GET /v1/sandboxes/{id}` |

Rules that matter:

- Do not construct `urls.proxy`, `urls.mcp`, or `urls.web` by hand.
- Use `sandbox_id` for follow-up operations; `name` is only a human label.
- Data-plane automation uses API keys, not browser session cookies.

## Quickstart

### 1. Install the CLI

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

### 2. Create a sandbox and export its endpoints

```bash
treadstone auth login
export TREADSTONE_API_KEY=$(treadstone --json api-keys create --name local --save | jq -r '.key')

SANDBOX_JSON=$(treadstone --json sandboxes create --template aio-sandbox-tiny --name demo)
export SANDBOX_ID=$(jq -r '.id' <<< "$SANDBOX_JSON")
export PROXY_URL=$(jq -r '.urls.proxy' <<< "$SANDBOX_JSON")
export MCP_URL=$(jq -r '.urls.mcp' <<< "$SANDBOX_JSON")
export WEB_URL=$(jq -r '.urls.web' <<< "$SANDBOX_JSON")

echo "$SANDBOX_JSON"
```

### 3. Run something inside the sandbox over the data plane

```bash
curl -sS -X POST "${PROXY_URL}/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"echo hello from treadstone && uname -a","exec_dir":"/tmp"}'
```

### 4. Connect an MCP client to the sandbox

Use `urls.mcp` from the sandbox response:

```json
{
  "mcpServers": {
    "treadstone-sandbox": {
      "url": "https://api.treadstone-ai.dev/v1/sandboxes/sb_xxx/proxy/mcp",
      "headers": {
        "Authorization": "Bearer sk_your_key_here"
      }
    }
  }
}
```

If you want a full Python example that combines control plane and data plane, see [`examples/data_plane/01_agent_sandbox_runtime.py`](examples/data_plane/01_agent_sandbox_runtime.py).

## Documentation

- [Quickstart](https://treadstone-ai.dev/docs/quickstart)
- [Sandbox lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle)
- [Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox)
- [MCP in sandbox](https://treadstone-ai.dev/docs/mcp-sandbox)
- [CLI guide](https://treadstone-ai.dev/docs/cli-guide)
- [Python SDK guide](https://treadstone-ai.dev/docs/python-sdk-guide)
- [REST API guide](https://treadstone-ai.dev/docs/rest-api-guide)
- [API reference](https://treadstone-ai.dev/docs/api-reference)
- [Deploy / self-hosting notes](deploy/README.md)

### OpenAPI note

The hosted OpenAPI document at [`https://api.treadstone-ai.dev/openapi.json`](https://api.treadstone-ai.dev/openapi.json) includes merged sandbox runtime paths under `/v1/sandboxes/{sandbox_id}/proxy/...`, and the hosted Swagger UI shows them under tags like `Sandbox: shell`, `Sandbox: file`, and `Sandbox: browser`.

The generated Python SDK is built from a public export that intentionally omits those merged runtime paths. Use hosted Swagger or raw HTTP when you need the full data-plane contract.

## Python SDK

```bash
pip install treadstone-sdk
```

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk_your_api_key",
)

templates = sandbox_templates_list_sandbox_templates.sync(client=client)
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(
        template=templates.items[0].name,
        name="demo",
    ),
)

print(sandbox.id)
print(sandbox.urls.proxy)
print(sandbox.urls.mcp)
```

For Python-side runtime control inside the sandbox, pair the control-plane SDK with `agent-sandbox` as shown in [`examples/README.md`](examples/README.md).

## Built-in sandbox tiers

The demo and production charts define five AIO templates:

| Template | CPU | Memory | Storage options |
| --- | --- | --- | --- |
| `aio-sandbox-tiny` | 0.25 vCPU | 1 GiB | `5Gi`, `10Gi`, `20Gi` |
| `aio-sandbox-small` | 0.5 vCPU | 2 GiB | `5Gi`, `10Gi`, `20Gi` |
| `aio-sandbox-medium` | 1 vCPU | 4 GiB | `5Gi`, `10Gi`, `20Gi` |
| `aio-sandbox-large` | 2 vCPU | 8 GiB | `5Gi`, `10Gi`, `20Gi` |
| `aio-sandbox-xlarge` | 4 vCPU | 16 GiB | `5Gi`, `10Gi`, `20Gi` |

Examples:

```bash
treadstone sandboxes create --template aio-sandbox-tiny --name quick-demo
treadstone sandboxes create --template aio-sandbox-large --name dev-box --persist --storage-size 5Gi
treadstone sandboxes snapshot <sandbox_id>
```

## Architecture

At a high level, Treadstone is:

- a FastAPI-based control plane for auth, API keys, lifecycle, usage, and browser handoff
- a Kubernetes-backed sandbox orchestration layer built around the `agent-sandbox` controller
- an all-in-one sandbox runtime image exposed through proxy and subdomain surfaces
- a self-hostable system with usage metering, plan enforcement, and multi-tenant boundaries

Core implementation pieces in this repo:

- `treadstone/` — API server and platform services
- `cli/` — `treadstone` CLI
- `sdk/python/` — generated Python SDK
- `deploy/` — Helm charts and local/prod deployment assets
- `examples/` — control-plane and data-plane usage examples

## Develop locally

```bash
make install
make dev-api
make dev-web
make test
make lint
make local
```

More details:

- local and production deploy flow: [`deploy/README.md`](deploy/README.md)
- end-to-end examples: [`examples/README.md`](examples/README.md)
- Chinese internal docs: [`docs/zh-CN/README.md`](docs/zh-CN/README.md)

## Community

- [Discord](https://discord.gg/ygSP9tT5RB)
- [X / Twitter](https://x.com/treadstone_ai)
