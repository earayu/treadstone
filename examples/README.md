# Treadstone Examples

Step-by-step examples for creating, managing, and interacting with Treadstone sandboxes.

## Architecture Overview

Treadstone is built around two distinct planes:

```
┌──────────────────────────────────────────────────────────┐
│                   Your application                        │
│                                                          │
│   ┌─────────────────────┐   ┌──────────────────────────┐ │
│   │   Control Plane      │   │      Data Plane          │ │
│   │   (Treadstone API)   │   │   (Sandbox Runtime)      │ │
│   │                      │   │                          │ │
│   │  • Create sandbox    │   │  • Execute shell cmds    │ │
│   │  • List sandboxes    │   │  • Read / write files    │ │
│   │  • Start / stop      │   │  • Control browser       │ │
│   │  • Delete sandbox    │   │  • Run Jupyter / Node.js │ │
│   │  • Manage API keys   │   │  • Use MCP tools         │ │
│   └──────────┬───────────┘   └──────────┬───────────────┘ │
│              │                          │                  │
│     treadstone_sdk                agent_sandbox            │
│     AuthenticatedClient            Sandbox(base_url=       │
│                                     sandbox.urls.proxy)    │
└──────────────────────────────────────────────────────────┘
```

**Control plane** manages sandbox lifecycle and is accessed via `treadstone_sdk`.

**Data plane** runs operations *inside* a sandbox. You reach it through the proxy
URL (`sandbox_detail.urls.proxy`) returned by the control plane, and interact with
it using `agent_sandbox.Sandbox`.

### Connecting the two planes

```python
# 1. Control plane: create a sandbox and get its proxy URL
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_get_sandbox

ctrl = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="<api-key>")
detail = sandboxes_get_sandbox.sync(sandbox_id="<id>", client=ctrl)
proxy_url = detail.urls.proxy          # e.g. "https://…/v1/sandboxes/<id>/proxy"

# 2. Data plane: connect agent-sandbox to the proxy URL
from agent_sandbox import Sandbox

sb = Sandbox(
    base_url=proxy_url,
    headers={"Authorization": "Bearer <data-plane-key>"},
)
result = sb.shell.exec_command(command="ls -la")
```

## Prerequisites

```bash
pip install treadstone-sdk agent-sandbox
```

You need a control-plane API key. Set it as an environment variable or pass it via `--api-key`:

```bash
export TREADSTONE_API_KEY=<your-key>
```

## Examples

| File | What it shows |
|------|--------------|
| [`01_create.py`](01_create.py) | List templates, create a sandbox, wait for ready |
| [`02_list.py`](02_list.py) | List all sandboxes, group by status |
| [`03_lifecycle.py`](03_lifecycle.py) | Stop and start a sandbox (status transitions) |
| [`04_data_plane.py`](04_data_plane.py) | Shell, file, browser, and Jupyter operations |

Run any example with `--help` for full options:

```bash
python examples/01_create.py --help
```

## Quick Start

### 1. Create a sandbox

```bash
python examples/01_create.py --api-key $TREADSTONE_API_KEY
```

This creates a sandbox, waits for it to become ready, prints its proxy URL, and
then deletes it. Pass `--keep` to leave the sandbox running.

### 2. List your sandboxes

```bash
python examples/02_list.py --api-key $TREADSTONE_API_KEY

# Filter by status:
python examples/02_list.py --api-key $TREADSTONE_API_KEY --status ready
```

### 3. Stop and start a sandbox

```bash
# Use an existing sandbox:
python examples/03_lifecycle.py --api-key $TREADSTONE_API_KEY --sandbox-id <id>

# Or let the example create a temporary one:
python examples/03_lifecycle.py --api-key $TREADSTONE_API_KEY
```

### 4. Run data-plane operations

```bash
# Use an existing ready sandbox (fastest):
python examples/04_data_plane.py --api-key $TREADSTONE_API_KEY --sandbox-id <id>

# Or create a temporary sandbox for the demo:
python examples/04_data_plane.py --api-key $TREADSTONE_API_KEY
```

This example covers:
- **Shell**: execute arbitrary commands, capture stdout / exit code
- **File**: write a file, read it back, list a directory
- **Browser**: fetch viewport info, take a PNG screenshot
- **Jupyter**: run Python code in a persistent kernel, capture outputs

## API Reference

The full OpenAPI specification — including sandbox runtime endpoints accessible
through the proxy — is available at:

```
GET <base-url>/openapi.json
```

Or browse it interactively in the Swagger UI:

```
<base-url>/docs
```

The proxy routes are documented under the **"Sandbox: ..."** tag sections
(e.g. "Sandbox: shell", "Sandbox: file", "Sandbox: browser").
