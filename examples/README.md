# Treadstone Examples

Runnable samples aligned with the public docs in `web/public/docs/`. They are grouped by **control plane** (Treadstone API for lifecycle, keys, handoff) vs **data plane** (HTTP into a running sandbox via `urls.proxy`).

## Architecture

Treadstone is two planes:

```
┌──────────────────────────────────────────────────────────┐
│                   Your application                        │
│                                                          │
│   ┌─────────────────────┐   ┌──────────────────────────┐ │
│   │   Control plane      │   │      Data plane         │ │
│   │   (Treadstone API)   │   │   (Sandbox runtime)     │ │
│   │                      │   │                          │ │
│   │  • Create sandbox    │   │  • Shell / file / browser │ │
│   │  • List / get        │   │  • Jupyter, MCP, …       │ │
│   │  • Stop / start      │   │                          │ │
│   │  • Delete            │   │                          │ │
│   │  • Web-link handoff  │   │                          │ │
│   └──────────┬───────────┘   └──────────┬───────────────┘ │
│              │                          │                  │
│     treadstone_sdk                agent_sandbox            │
│     AuthenticatedClient            Sandbox(base_url=       │
│                                     sandbox.urls.proxy)    │
└──────────────────────────────────────────────────────────┘
```

**Connecting the two planes**

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_get_sandbox

ctrl = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="<api-key>")
detail = sandboxes_get_sandbox.sync(sandbox_id="<id>", client=ctrl)
proxy_url = detail.urls.proxy

from agent_sandbox import Sandbox

sb = Sandbox(
    base_url=proxy_url,
    headers={"Authorization": "Bearer <data-plane-key>"},
)
result = sb.shell.exec_command(command="ls -la")
```

See [Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox.md) and [API Keys & Auth](https://treadstone-ai.dev/docs/api-keys-auth.md) for keys and scopes.

## Prerequisites

```bash
pip install treadstone-sdk agent-sandbox   # data-plane agent example only
pip install treadstone-sdk httpx           # httpx data-plane example only
```

Set a control-plane API key:

```bash
export TREADSTONE_API_KEY=<your-key>
```

Or pass `--api-key` on each run. Create a key with `treadstone api-keys create --name local --save` (see [Quickstart](https://treadstone-ai.dev/docs/quickstart.md)).

## Layout

| Path | Maps to docs | What it shows |
|------|----------------|---------------|
| [`control_plane/01_create_sandbox.py`](control_plane/01_create_sandbox.py) | [Quickstart](https://treadstone-ai.dev/docs/quickstart.md), [Sandbox lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle.md) | List templates, create sandbox, wait for `ready`, optional delete |
| [`control_plane/02_list_sandboxes.py`](control_plane/02_list_sandboxes.py) | [Sandbox lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle.md) | List sandboxes, group by status, optional `--status` filter |
| [`control_plane/03_lifecycle_stop_start.py`](control_plane/03_lifecycle_stop_start.py) | [Sandbox lifecycle](https://treadstone-ai.dev/docs/sandbox-lifecycle.md) | Stop → start transitions |
| [`control_plane/04_browser_handoff.py`](control_plane/04_browser_handoff.py) | [Browser handoff](https://treadstone-ai.dev/docs/browser-handoff.md) | `web-link` create, status, delete, create again |
| [`data_plane/01_agent_sandbox_runtime.py`](data_plane/01_agent_sandbox_runtime.py) | [Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox.md) | Scoped data-plane key + `agent_sandbox`: shell, file, browser, Jupyter |
| [`data_plane/02_httpx_proxy_shell_exec.py`](data_plane/02_httpx_proxy_shell_exec.py) | [REST API guide](https://treadstone-ai.dev/docs/rest-api-guide.md), [Inside your sandbox](https://treadstone-ai.dev/docs/inside-sandbox.md) | Minimal `httpx` `POST /v1/shell/exec` via `urls.proxy` (no `agent-sandbox`) |

Shared helpers: [`_shared.py`](_shared.py).

## Run

From the repository root:

```bash
python examples/control_plane/01_create_sandbox.py --help
python examples/control_plane/01_create_sandbox.py --api-key "$TREADSTONE_API_KEY"

python examples/control_plane/02_list_sandboxes.py --api-key "$TREADSTONE_API_KEY"
python examples/control_plane/02_list_sandboxes.py --api-key "$TREADSTONE_API_KEY" --status ready

python examples/control_plane/03_lifecycle_stop_start.py --api-key "$TREADSTONE_API_KEY" --sandbox-id <id>
python examples/control_plane/03_lifecycle_stop_start.py --api-key "$TREADSTONE_API_KEY"

python examples/control_plane/04_browser_handoff.py --api-key "$TREADSTONE_API_KEY" --sandbox-id <id>

python examples/data_plane/01_agent_sandbox_runtime.py --api-key "$TREADSTONE_API_KEY" --sandbox-id <id>
python examples/data_plane/02_httpx_proxy_shell_exec.py --api-key "$TREADSTONE_API_KEY" --sandbox-id <id>
```

## API reference

Full OpenAPI (including merged sandbox runtime paths under the proxy) is served by the API, e.g. `GET https://api.treadstone-ai.dev/openapi.json` and [Swagger UI](https://api.treadstone-ai.dev/docs). The Python SDK used here is generated from a **public** export that omits merged proxy paths; use hosted Swagger for data-plane HTTP contract details. See [Python SDK guide](https://treadstone-ai.dev/docs/python-sdk-guide.md).
