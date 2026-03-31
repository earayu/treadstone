# REST API Guide

Use this page when you integrate over HTTP in any language, without going through the CLI or Python SDK. Treadstone exposes two HTTP surfaces, not one:

1. **Control plane** — On the hosted cloud this is `https://api.treadstone-ai.dev/v1/...`. You call Treadstone itself: auth, templates, sandboxes, usage, issuing handoff links, and so on. The contract is in the [API Reference](/docs/api-reference.md). Self-hosted deployments use their own origin with the same `/v1/...` layout.

2. **Data plane** — The `urls.proxy` value from a running sandbox (or the equivalent path `/v1/sandboxes/{sandbox_id}/proxy/{path}` on the API host). You use it to reach HTTP services inside the sandbox, not to manage the platform. Treadstone strips the proxy prefix and forwards the request into the container; method, path after `/proxy/`, headers, and body follow the rules in the [API Reference](/docs/api-reference.md). Take `urls.proxy` from API output; do not invent hostnames.

Auth differs between these surfaces. The data plane accepts API keys only. Read [API Keys & Auth](/docs/api-keys-auth.md). This page focuses on how the control-plane REST shape fits together: base URL, headers, JSON, errors. It does not repeat sandbox lifecycle, key semantics, or browser handoff; see [Sandbox Lifecycle](/docs/sandbox-lifecycle.md) and [Browser Handoff](/docs/browser-handoff.md) when you need those workflows.

## Prerequisites

- A control-plane base URL (hosted: `https://api.treadstone-ai.dev`, or your self-hosted URL).
- An API key for service-to-service calls. Create and scope keys as described in [API Keys & Auth](/docs/api-keys-auth.md); do not paste long-lived secrets into prompts or logs.

## How REST is shaped

### Versioning and health

- Health (no version prefix): `GET /health` — small JSON such as `{"status":"ok"}`. Listed under System in the [API Reference](/docs/api-reference.md).
- Control plane API: paths under `/v1/...`. On the hosted product, use `https://api.treadstone-ai.dev` as the origin and append `/v1/sandboxes`, etc. Self-hosted: substitute your control-plane origin.

Always use HTTPS against production.

### Headers you actually need

| Concern | What to send |
|---------|----------------|
| Authentication | `Authorization: Bearer <api_key>` on routes that require auth. |
| JSON bodies | `Content-Type: application/json` with a UTF-8 JSON body. |
| Request shape | Use the HTTP method, path, and JSON fields documented in the [API Reference](/docs/api-reference.md) for each operation. |

The control plane can accept a session cookie for browser-driven flows. For automation and server-to-server work, prefer API keys only; do not rely on cookie jars in your backend.

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

Use `urls.proxy` from `GET /v1/sandboxes/{sandbox_id}` (or `treadstone sandboxes get`) as the base URL for HTTP into the sandbox. Append the path your app serves after the `/proxy` segment: the first path segment after `/proxy/` is what the workload inside the container receives (see the [API Reference](/docs/api-reference.md) for hop filtering). Data plane requests use `Authorization: Bearer <api_key>` only, not a Console session cookie ([API Keys & Auth](/docs/api-keys-auth.md)).

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

## Read Next

- [Sandbox endpoints](/docs/sandbox-endpoints.md)
- [API Reference](/docs/api-reference.md)
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP servers behind `urls.proxy`
- [Error Reference](/docs/error-reference.md)
- [Python SDK Guide](/docs/python-sdk-guide.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
