# Python SDK Guide

## What this page is for

Use this when you want **typed** request/response models and **httpx**-backed calls in Python against the public Treadstone OpenAPI surface, instead of hand-written `requests` or `curl`.

This page covers **SDK-only** topics: install, `AuthenticatedClient`, package layout, and the `sync` / `sync_detailed` / `asyncio` / `asyncio_detailed` entry points. It does **not** repeat sandbox lifecycle, auth, or browser handoff — see [CLI Guide](/docs/cli-guide.md), [API Keys & Auth](/docs/api-keys-auth.md), and [Sandbox Lifecycle](/docs/sandbox-lifecycle.md). Per-endpoint imports and types: [Python SDK Reference](/docs/python-sdk-reference.md).

## Use this when

- You are building a Python service or script that calls the control plane API.
- You want generated models and a consistent error surface instead of ad hoc JSON parsing.
- You are fine regenerating the SDK when the OpenAPI contract changes (see [Regeneration and scope](#regeneration-and-scope)).

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

- `base_url` — Control plane origin **without** a trailing slash; paths such as `/v1/sandboxes` are appended by the generated code.
- `token` — Your API key string. The client sets `Authorization: Bearer` on each request.
- Optional behavior (defaults are usually fine): `raise_on_unexpected_status`, `timeout`, and the underlying httpx client — inspect generated `AuthenticatedClient` in the package if you need custom timeouts or TLS.

Use `AuthenticatedClient` for any route that requires authentication. There is also an unauthenticated `Client` for the few public endpoints, if present in your generated tree.

## How the package is organized

Generation follows OpenAPI tags and operation IDs:

- **Endpoint modules**: `treadstone_sdk.api.<tag>.<operation_module>` (for example `treadstone_sdk.api.sandboxes.sandboxes_list_sandboxes`). The tag matches the API docs sections (sandboxes, auth, usage, …).
- **Models**: `treadstone_sdk.models` — Pydantic-style types for bodies and responses (`CreateSandboxRequest`, `SandboxDetailResponse`, …).

To find a function, start from the REST path in [API Reference](/docs/api-reference.md), then locate the matching module in [Python SDK Reference](/docs/python-sdk-reference.md) or by browsing `treadstone_sdk.api` in your editor.

## Call shapes: `sync` vs `detailed` vs `asyncio`

Each operation exposes four entry points:

| Shape | Returns | When to use |
|-------|---------|-------------|
| `sync` | Parsed model (or `None` / validation type depending on status) | Normal synchronous code paths. |
| `sync_detailed` | `Response[...]` with `status_code`, raw `content`, `headers`, and `parsed` | When you need status codes, headers, or raw bytes without losing parsing. |
| `asyncio` | Same idea as `sync`, but async | `async def` services and asyncio apps. |
| `asyncio_detailed` | Async variant of `sync_detailed` | Async + full response object. |

On unexpected HTTP status codes, behavior depends on `raise_on_unexpected_status`: the client may raise `UnexpectedStatus` (see `treadstone_sdk.errors`) or return `None` for the parsed body. Always handle httpx network errors (`TimeoutException`, etc.) in production code. For HTTP error body shape from the server, see [Error Reference](/docs/error-reference.md).

## Regeneration and scope

The SDK is regenerated from the **public** OpenAPI spec (admin and internal-only routes are excluded from the published package). That export does **not** include merged **sandbox-runtime** paths that appear under `/v1/sandboxes/{sandbox_id}/proxy/...` in the **hosted** [`/openapi.json`](https://api.treadstone-ai.dev/openapi.json) and [Swagger UI](https://api.treadstone-ai.dev/docs) — use those when you need OpenAPI for workloads inside the sandbox.

If you change control-plane routes and need new Python types, regenerate with `make gen-sdk-python` in this repository (see `AGENTS.md`). Do not hand-edit generated files under `sdk/python/` in the upstream project.

## Read next

- [Python SDK Reference](/docs/python-sdk-reference.md)
- [REST API Guide](/docs/rest-api-guide.md) — Same API, raw HTTP view
- [CLI Guide](/docs/cli-guide.md) — Terminal integration
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP URLs and data plane
- [API Reference](/docs/api-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [Error Reference](/docs/error-reference.md)
