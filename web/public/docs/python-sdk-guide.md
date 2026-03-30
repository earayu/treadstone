# Python SDK Guide

Use this when you already live in Python and want generated models instead of hand-written requests.

## Install

```bash
pip install treadstone-sdk
```

## Create A Client

```python
from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",
)
```

## Create A Sandbox And Browser Handoff

```python
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox, sandboxes_create_sandbox_web_link
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template="aio-sandbox-tiny", name="agent-demo"),
)

session = sandboxes_create_sandbox_web_link.sync(sandbox.id, client=client)
print(sandbox.id)
print(session.open_link)
```

## What To Keep In Mind

- The SDK mirrors the OpenAPI tags. It is not a handwritten service layer.
- Request models live under `treadstone_sdk.models`.
- Endpoint modules live under `treadstone_sdk.api.<tag>`.
- Every endpoint exposes sync and async variants.

> For automation: keep `sandbox.id` and `session.open_link` from the SDK response. Do not rebuild those values.

## Read Next

- [Python SDK Reference](/docs/python-sdk-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
