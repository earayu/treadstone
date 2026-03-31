# REST API Guide

## What this page is for

Read this when you integrate **over HTTP in any language** (not via the [CLI](/docs/cli-guide.md) or [Python SDK](/docs/python-sdk-guide.md)). It explains how the **control plane** and **data plane** URLs fit together, which **headers** and **JSON** shapes to expect, and how to call the **sandbox proxy** from `curl` or httpx.

It does **not** walk through lifecycle, key scoping, or browser handoff step by step — use [Sandbox Lifecycle](/docs/sandbox-lifecycle.md), [API Keys & Auth](/docs/api-keys-auth.md), and [Browser Handoff](/docs/browser-handoff.md) for those workflows. The full route list is in [API Reference](/docs/api-reference.md).

## The two HTTP surfaces

Treadstone exposes two surfaces, not one:

1. **Control plane** — On hosted cloud: `https://api.treadstone-ai.dev/v1/...`. You call Treadstone for auth, templates, sandboxes, usage, handoff links, and so on. Self-hosted deployments use their own origin with the same `/v1/...` layout.

2. **Data plane** — The `urls.proxy` value from a running sandbox (or the path `/v1/sandboxes/{sandbox_id}/proxy/{path}` on the API host). You use it to reach HTTP services **inside** the sandbox, not to manage the platform. Treadstone strips the proxy prefix and forwards into the container. Take `urls.proxy` from API output; do not invent hostnames.

Auth differs: the data plane accepts **API keys only**. See [API Keys & Auth](/docs/api-keys-auth.md).

## Prerequisites

- A control-plane base URL (hosted: `https://api.treadstone-ai.dev`, or your self-hosted URL).
- An API key for service-to-service calls. Create and scope keys as in [API Keys & Auth](/docs/api-keys-auth.md); do not paste long-lived secrets into prompts or logs.

## How REST is shaped

### Versioning and health

- **Health** (no version prefix): `GET /health` — small JSON such as `{"status":"ok"}`. Listed under System in [API Reference](/docs/api-reference.md).
- **Control plane API**: paths under `/v1/...`. On hosted product, use `https://api.treadstone-ai.dev` as the origin and append `/v1/sandboxes`, etc.

Always use HTTPS in production.

### Headers you actually need

| Concern | What to send |
|---------|----------------|
| Authentication | `Authorization: Bearer <api_key>` on routes that require auth. |
| JSON bodies | `Content-Type: application/json` with a UTF-8 JSON body. |
| Request shape | Use the HTTP method, path, and JSON fields documented in [API Reference](/docs/api-reference.md) for each operation. |

The control plane can accept a session cookie for browser-driven flows. For automation and server-to-server work, prefer **API keys**; do not rely on cookie jars in your backend.

### Bodies and responses

- Successful responses are JSON unless the route is documented otherwise.
- Errors use a stable JSON envelope (`error.code`, `error.message`, `error.status`, etc.). Treat 4xx/5xx bodies as structured data. Full shape and codes: [Error Reference](/docs/error-reference.md).

### Control plane vs data plane (REST view)

| | Control plane | Data plane |
|---|----------------|------------|
| What you are calling | The Treadstone platform | A sandbox’s internal HTTP server (via reverse proxy) |
| Typical paths | `/v1/auth/*`, `/v1/sandboxes`, `/v1/usage`, … | `urls.proxy` … `/proxy/{path}` — `{path}` is forwarded inside the container |
| Auth | `Authorization: Bearer` and/or browser session where applicable | API keys only; session cookies do not apply. Narrow keys with `data_plane` scope when possible ([API Keys & Auth](/docs/api-keys-auth.md)). |

Do not guess `urls.proxy`, `open_link`, or `web_url` — take them from API responses.

In the Console Sandboxes table, Web, MCP, and Proxy map to `urls.web`, `urls.mcp`, and `urls.proxy`. See [Sandbox endpoints](/docs/sandbox-endpoints.md).

## How to use the data-plane proxy

Use `urls.proxy` from `GET /v1/sandboxes/{sandbox_id}` (or `treadstone sandboxes get`) as the base URL for HTTP into the sandbox. Append the path your app serves after the `/proxy` segment: the first path segment after `/proxy/` is what the workload inside the container receives (see [API Reference](/docs/api-reference.md) for hop filtering). Data-plane requests use `Authorization: Bearer <api_key>` only, not a Console session cookie ([API Keys & Auth](/docs/api-keys-auth.md)).

Replace `sb_xxx` and keys with values from your environment.

### cURL

```bash
export TREADSTONE_API_KEY="sk_..."
export PROXY_BASE="https://api.treadstone-ai.dev/v1/sandboxes/sb_xxx/proxy"

curl -sS "$PROXY_BASE/health" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python (httpx)

```python
import os

import httpx

proxy_base = os.environ["SANDBOX_PROXY_URL"]  # urls.proxy from GET /v1/sandboxes/{id}
api_key = os.environ["TREADSTONE_API_KEY"]

with httpx.Client(
    base_url=proxy_base.rstrip("/"),
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30.0,
) as client:
    r = client.get("/health")  # forwarded inside the container as GET /health
    r.raise_for_status()
    print(r.text)
```

`urls.proxy` is usually without a trailing slash; join paths so you do not double up slashes.

### Discovering the contract

The server exposes OpenAPI at `/openapi.json` (public, code-first spec). On the hosted control plane, open [https://api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs) for Swagger UI. Use the JSON spec to generate clients or to inspect schemas when something is ambiguous. The hosted product’s public routes match what the Python SDK is generated from.

## Read next

- [CLI Guide](/docs/cli-guide.md) — same platform, terminal and flags
- [Python SDK Guide](/docs/python-sdk-guide.md) — same API, generated client
- [Sandbox endpoints](/docs/sandbox-endpoints.md) — Web, MCP, Proxy in the Console
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP behind `urls.proxy`
- [API Reference](/docs/api-reference.md)
- [Error Reference](/docs/error-reference.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
