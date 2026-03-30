# Quickstart for Python SDK

## What this page is for

Show the shortest real Python SDK flow using the generated package that exists in this repo today.

## Use this when

- You want typed request and response models.
- You prefer generated `httpx` clients over hand-written REST requests.
- You need a Python example that matches the actual SDK module layout.

## Shortest path

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.auth import auth_get_user
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox, sandboxes_create_sandbox_web_link
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",
)

user = auth_get_user.sync(client=client)
sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(template="aio-sandbox-tiny", name="sdk-demo"),
)
link = sandboxes_create_sandbox_web_link.sync(sandbox_id=sandbox.id, client=client)
print(user.email, sandbox.id, sandbox.urls.proxy, link.open_link)
```

## Hard rules

- Use `AuthenticatedClient` for protected endpoints.
- Import from generated endpoint modules such as `treadstone_sdk.api.sandboxes`.
- Create request bodies with generated models such as `CreateSandboxRequest`.
- The SDK mirrors the API. It is not a handwritten object wrapper.

## Install

```bash
pip install treadstone-sdk
```

## Sync Example

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_get_sandbox

client = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="sk-...")
sandbox = sandboxes_get_sandbox.sync("sb...", client=client)
print(sandbox.status)
```

## Async Example

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

client = AuthenticatedClient(base_url="https://api.treadstone-ai.dev", token="sk-...")

async def main() -> None:
    async with client:
        sandbox = await sandboxes_create_sandbox.asyncio(
            client=client,
            body=CreateSandboxRequest(template="aio-sandbox-tiny", name="sdk-async"),
        )
        print(sandbox.id)
```

## What to Capture

- `sandbox.id`
- `sandbox.urls.proxy`
- `sandbox.urls.web`
- `link.open_link`

## For Agents

- If you want the fewest tokens and the clearest control flow, the REST or CLI quickstarts are shorter than the SDK.
- If you need typed payloads and Python-native calling style, the SDK is the right surface.
