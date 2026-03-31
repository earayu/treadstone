# Python SDK Guide

The **`treadstone-sdk`** package is a **generated** HTTP client for the **public** Treadstone OpenAPI surface. Use it when you want **typed** request/response models and `httpx`-backed calls in Python, instead of hand-written `requests` or `curl`.

This page covers **SDK-only** topics: install, `AuthenticatedClient`, module layout, and the **`sync` / `sync_detailed` / `asyncio` / `asyncio_detailed`** call shapes. It does **not** walk through sandbox creation, auth, or handoff again — see [CLI Guide](/docs/cli-guide.md), [API Keys & Auth](/docs/api-keys-auth.md), and [Sandbox Lifecycle](/docs/sandbox-lifecycle.md). Endpoint-by-endpoint names and types: [Python SDK Reference](/docs/python-sdk-reference.md).

## Install

```bash
pip install treadstone-sdk
```

Pin versions in applications; upgrade when you intentionally adopt new API behavior.

## The client

```python
from treadstone_sdk import AuthenticatedClient

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",  # API key; same credential model as REST Bearer auth
)
```

- **`base_url`** — control plane origin **without** a trailing slash; paths such as `/v1/sandboxes` are appended by the generated code.
- **`token`** — your API key string. The client sets the **`Authorization: Bearer`** header on each request.
- Optional behavior (defaults are usually fine): **`raise_on_unexpected_status`**, **`timeout`**, and the underlying **`httpx`** client — see the generated `AuthenticatedClient` in the package if you need custom timeouts or TLS.

Use **`AuthenticatedClient`** for any route that requires authentication. There is also an unauthenticated **`Client`** for the few public endpoints, if present in your generated tree.

## How the package is organized

Generation follows **OpenAPI tags** and operation IDs:

- **Endpoint modules** — `treadstone_sdk.api.<tag>.<operation_module>` (for example `treadstone_sdk.api.sandboxes.sandboxes_list_sandboxes`). The **tag** matches the API docs sections (sandboxes, auth, usage, …).
- **Models** — `treadstone_sdk.models` — Pydantic-style types for bodies and responses (`CreateSandboxRequest`, `SandboxDetailResponse`, …).

To find a function, start from the **REST path** in [API Reference](/docs/api-reference.md), then locate the matching module in [Python SDK Reference](/docs/python-sdk-reference.md) or by browsing `treadstone_sdk.api` in your editor.

## Call shapes: `sync` vs `detailed` vs `asyncio`

Each operation exposes four entry points:

| Shape | Returns | When to use |
|-------|---------|-------------|
| **`sync`** | Parsed model (or `None` / validation type depending on status) | Normal synchronous code paths. |
| **`sync_detailed`** | `Response[...]` with **`status_code`**, raw **`content`**, **`headers`**, and **`parsed`** | When you need status codes, headers, or raw bytes without losing parsing. |
| **`asyncio`** | Same idea as `sync`, but **async** | `async def` services and asyncio apps. |
| **`asyncio_detailed`** | Async variant of `sync_detailed` | Async + full response object. |

On **unexpected HTTP status codes**, behavior depends on **`raise_on_unexpected_status`**: the client may raise **`UnexpectedStatus`** (see `treadstone_sdk.errors`) or return **`None`** for the parsed body. Always handle **`httpx`** network errors (`TimeoutException`, etc.) in production code.

## Regeneration and scope

The SDK is **regenerated from the public OpenAPI spec** (admin and internal-only routes are excluded from the published package). If you change server routes and need new Python types, regenerate with the repo’s tooling — see **`make gen-sdk-python`** in the Treadstone developer docs / `AGENTS.md`. Do not hand-edit generated files under `sdk/python/` in the upstream project.

## Read Next

- [Python SDK Reference](/docs/python-sdk-reference.md)
- [REST API Guide](/docs/rest-api-guide.md) — same API, raw HTTP view
- [API Reference](/docs/api-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
