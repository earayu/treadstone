# treadstone-sdk

Typed Python SDK for the Treadstone sandbox service.

## Install

```bash
pip install treadstone-sdk
```

## Client types

Use `Client` for unauthenticated endpoints such as health checks:

```python
from treadstone_sdk import Client
from treadstone_sdk.api.system import system_health

client = Client(base_url="https://api.example.com")
health = system_health.sync(client=client)
print(health.status)
```

Use `AuthenticatedClient` for protected endpoints. For AI agents and automation,
an API key is the preferred credential:

```python
from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.example.com",
    token="sk_your_api_key",
)
```

## Common sandbox workflow

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandbox_templates import sandbox_templates_list_sandbox_templates
from treadstone_sdk.api.sandboxes import (
    sandboxes_create_sandbox,
    sandboxes_create_sandbox_web_link,
    sandboxes_get_sandbox,
)
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(base_url="https://api.example.com", token="sk_your_api_key")

templates = sandbox_templates_list_sandbox_templates.sync(client=client)
template_name = templates.items[0].name

sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(
        template=template_name,
        name="demo",
    ),
)

sandbox_id = sandbox.id
detail = sandboxes_get_sandbox.sync(sandbox_id=sandbox_id, client=client)
web_link = sandboxes_create_sandbox_web_link.sync(sandbox_id=sandbox_id, client=client)

print(sandbox_id)
print(detail.urls.proxy)
print(web_link.open_link)
```

## Async example

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_get_sandbox

client = AuthenticatedClient(base_url="https://api.example.com", token="sk_your_api_key")

async with client:
    sandbox = await sandboxes_get_sandbox.asyncio("sbabc123def456", client=client)
    print(sandbox.status)
```

## Important identifier rules

- `sandbox.name` is a human-readable label scoped to the current user.
- Follow-up sandbox operations use `sandbox.id`.
- Browser entry URLs are based on `sandbox_id` under the hood.
- Do not construct Web UI URLs from sandbox names. Read `sandbox.urls.web`, `web_url`, or `open_link` from API responses.

## Generated module layout

The SDK is generated from the OpenAPI spec:

- API functions live under `treadstone_sdk.api.<tag>`
- Request and response models live under `treadstone_sdk.models`
- Each endpoint exposes `sync`, `sync_detailed`, `asyncio`, and `asyncio_detailed`

Example imports:

```python
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
```

## Transport customization

You can customize the underlying `httpx` clients if needed:

```python
import httpx

from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.example.com",
    token="sk_your_api_key",
    httpx_args={"timeout": 60.0},
)

client.set_httpx_client(
    httpx.Client(
        base_url="https://api.example.com",
        headers={"Authorization": "Bearer sk_your_api_key"},
        timeout=60.0,
    )
)
```

For internal environments with a custom CA bundle:

```python
client = AuthenticatedClient(
    base_url="https://internal-api.example.com",
    token="sk_your_api_key",
    verify_ssl="/path/to/certificate_bundle.pem",
)
```
