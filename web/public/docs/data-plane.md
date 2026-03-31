# Using the data plane

## What this page is for

This page is the **hands-on path** for calling HTTP (or WebSocket) **workloads inside a sandbox** through Treadstone’s proxy. You already know control plane vs data plane in theory ([Sandbox endpoints](/docs/sandbox-endpoints.md)); here we focus on **what to do**: get URLs, pick an API key, send `curl` or client traffic, and avoid the usual mistakes.

It does **not** replace [Sandbox Lifecycle](/docs/sandbox-lifecycle.md) (create/start/stop/delete) or [API Keys & Auth](/docs/api-keys-auth.md) (sign-up and scope model). Read those first if you are new.

## Prerequisites

1. A **running** sandbox (or one that is ready for traffic — see `status` on [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)).
2. An **API key** with **data-plane** access to that sandbox (`mode: all` or `mode: selected` with this `sandbox_id` in the allowlist). See [API Keys & Auth](/docs/api-keys-auth.md).
3. The **proxy base URL** from the platform — never guess hostnames or paths.

## Get the URLs (control plane, one call)

```bash
export TREADSTONE_API_KEY="sk_..."
treadstone --json sandboxes get SANDBOX_ID
# or: curl -sS "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID" \
#       -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

From the JSON, read **`urls.proxy`** (HTTP prefix into the sandbox) and, if you use MCP, **`urls.mcp`**. Those strings are authoritative; copy them from the response or from the Console Endpoints row ([Sandbox endpoints](/docs/sandbox-endpoints.md)).

## Call an HTTP route inside the sandbox (data plane)

Append the path your app serves **after** the `/proxy` segment. The first path segment after `/proxy/` is what the workload receives (see [API Reference](/docs/api-reference.md) for proxy behaviour).

```bash
export TREADSTONE_API_KEY="sk_..."
export PROXY_BASE="https://api.treadstone-ai.dev/v1/sandboxes/sb_xxx/proxy"

curl -sS "$PROXY_BASE/health" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

Rules that do not change:

- **Only** `Authorization: Bearer <api_key>` — **not** a Console session cookie.
- If your key uses **`selected`** data-plane mode, it must include this **`sandbox_id`**.
- **WebSocket**: same URL family; use the Bearer header, or `?token=sk-…` if the client cannot set WS headers (see [API Reference](/docs/api-reference.md#proxy)).

## MCP

If your workload speaks MCP, use **`urls.mcp`** from the same sandbox response (full URL to the MCP path). Config examples and client files live in [MCP in sandbox](/docs/mcp-sandbox.md).

## Browser workspace vs proxy

**`urls.web`** is for humans in a browser (session or handoff). Automation into **HTTP services** should use **`urls.proxy`** / **`urls.mcp`**, not `urls.web`, unless you deliberately use a browser flow — see [Browser Handoff](/docs/browser-handoff.md).

## Explore the contract

The hosted [Swagger UI](https://api.treadstone-ai.dev/docs) includes **merged** sandbox-runtime paths under `/v1/sandboxes/{sandbox_id}/proxy/...` so you can inspect REST shapes for traffic into the box. The Python SDK is generated from a different export; see [REST API Guide](/docs/rest-api-guide.md#discovering-the-contract).

## Read next

- [REST API Guide](/docs/rest-api-guide.md) — headers, errors, `curl`/httpx
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP-specific setup
- [API Reference](/docs/api-reference.md) — Proxy section and route tables
- [Sandbox endpoints](/docs/sandbox-endpoints.md) — Web / MCP / Proxy in the Console
- [API Keys & Auth](/docs/api-keys-auth.md) — scope and least privilege
