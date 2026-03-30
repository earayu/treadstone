# SDK Reference

The Treadstone Python SDK (`treadstone-sdk`) provides typed, async-capable access to all API endpoints. It is auto-generated from the OpenAPI spec.

## Installation

```bash
pip install treadstone-sdk
```

## Creating a Client

**Unauthenticated (public endpoints only):**

```python
from treadstone_sdk import Client

client = Client(base_url="https://api.treadstone-ai.dev")
```

**Authenticated (most endpoints require this):**

```python
from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk_your_api_key",
)
```

## Basic Usage

Every API endpoint becomes a Python module with four functions:

| Function | Description |
|----------|-------------|
| `sync` | Blocking — returns parsed data or `None` |
| `sync_detailed` | Blocking — always returns a `Response` object |
| `asyncio` | Async version of `sync` |
| `asyncio_detailed` | Async version of `sync_detailed` |

### List Templates and Create a Sandbox

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk_your_api_key",
)

# List available templates
templates = sandbox_templates_list_sandbox_templates.sync(client=client)

# Create a sandbox
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(
        template=templates.items[0].name,
        name="demo",
    ),
)

# Always use sandbox.id for follow-up operations
print(sandbox.id)
```

### Async Usage

```python
import asyncio
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_list_sandboxes

async def main():
    async with AuthenticatedClient(
        base_url="https://api.treadstone-ai.dev",
        token="sk_your_api_key",
    ) as client:
        sandboxes = await sandboxes_list_sandboxes.asyncio(client=client)
        for sb in sandboxes.items:
            print(sb.id, sb.name, sb.status)

asyncio.run(main())
```

### Detailed Response (with status code)

```python
from treadstone_sdk.api.sandboxes import sandboxes_get_sandbox
from treadstone_sdk.types import Response

response: Response = sandboxes_get_sandbox.sync_detailed(
    client=client,
    sandbox_id="sb_abc123",
)
print(response.status_code)
print(response.parsed)
```

## TLS / Certificate Configuration

```python
# Custom certificate bundle
client = AuthenticatedClient(
    base_url="https://internal.example.com",
    token="sk_...",
    verify_ssl="/path/to/certificate_bundle.pem",
)

# Disable verification (not recommended in production)
client = AuthenticatedClient(
    base_url="https://internal.example.com",
    token="sk_...",
    verify_ssl=False,
)
```

## Module Naming Convention

The SDK module name for each endpoint is derived from the first tag on the route:

- `treadstone_sdk.api.sandboxes` — sandbox lifecycle operations
- `treadstone_sdk.api.sandbox_templates` — template listing
- `treadstone_sdk.api.api_keys` — API key management
- `treadstone_sdk.api.auth` — authentication endpoints
- `treadstone_sdk.api.default` — untagged endpoints

## Agent Usage Pattern

For AI agents using the SDK in an automated pipeline:

```python
import os
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import (
    sandboxes_create_sandbox,
    sandboxes_get_sandbox,
    sandboxes_delete_sandbox,
)
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(
    base_url=os.environ["TREADSTONE_BASE_URL"],
    token=os.environ["TREADSTONE_API_KEY"],
)

# Create
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template="aio-sandbox-small", name="agent-task"),
)
sandbox_id = sandbox.id   # capture ID immediately

# Poll status
result = sandboxes_get_sandbox.sync(client=client, sandbox_id=sandbox_id)
print(result.status)

# Cleanup
sandboxes_delete_sandbox.sync(client=client, sandbox_id=sandbox_id)
```
