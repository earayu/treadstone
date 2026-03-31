# Python SDK Guide

The Python SDK is a generated client that mirrors the REST API. Use it when you already live in Python and want typed request models and response objects instead of hand-written HTTP calls. Every API endpoint is available as a module function with sync and async variants.

## Install

```bash
pip install treadstone-sdk
```

## Create A Client

```python
from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",  # your API key
)
```

`AuthenticatedClient` injects the `Authorization` header on every request. Use it for all authenticated routes.

## Create A Sandbox And Generate A Handoff URL

```python
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox, sandboxes_create_sandbox_web_link
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template="aio-sandbox-tiny", name="agent-demo"),
)

session = sandboxes_create_sandbox_web_link.sync(sandbox.id, client=client)
print(sandbox.id)         # use this for every follow-up operation
print(session.open_link)  # share this URL with a human
```

## How The SDK Is Organized

The SDK mirrors the API's tag structure:

- **Endpoint modules** live under `treadstone_sdk.api.<tag>`, where `<tag>` matches the API section (e.g., `sandboxes`, `auth`, `usage`).
- **Request models** live under `treadstone_sdk.models`.
- Each endpoint exposes four call shapes: `sync`, `sync_detailed`, `asyncio`, and `asyncio_detailed`. Use the `asyncio` variants in async contexts.

> For automation: keep `sandbox.id` and `session.open_link` from the SDK response. Do not rebuild those values from other fields.

## Read Next

- [Python SDK Reference](/docs/python-sdk-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
