# REST API Guide

Use this page when you integrate over **HTTP** (any language or runtime) — not the CLI or Python SDK. Everything below assumes you understand that Treadstone exposes **two different HTTP APIs**, not one:

1. **Control plane** — `https://<api-host>/v1/...` — you call **Treadstone itself**: auth, templates, sandboxes (create, start, stop, delete), usage, issuing `open_link`, and so on. This is the platform API documented in [API Reference](/docs/api-reference.md).

2. **Data plane** — the **`urls.proxy`** URL returned when a sandbox is running (equivalently: **`/v1/sandboxes/{sandbox_id}/proxy/{path}`** on the API host). You use this to talk to **whatever HTTP server runs inside the sandbox**, not to manage Treadstone. It behaves as a **reverse proxy**: Treadstone removes the proxy routing prefix, then forwards the request **through** to the container — same HTTP method, and the path after `/proxy/` is what reaches the app inside (headers and body are forwarded; see [API Reference](/docs/api-reference.md) for hop filtering). Always take `urls.proxy` from API output; do not invent hostnames.

Auth and credentials **differ** between these surfaces (for example, the data plane accepts **API keys only**). Read [API Keys & Auth](/docs/api-keys-auth.md) for the split. This page focuses on **how the control plane REST shape fits together** (base URL, headers, JSON, errors). It does **not** repeat sandbox lifecycle, key semantics, or browser handoff walkthroughs; see [Sandbox Lifecycle](/docs/sandbox-lifecycle.md), [API Keys & Auth](/docs/api-keys-auth.md), and [Browser Handoff](/docs/browser-handoff.md).

## Prerequisites

- A **control-plane base URL** (for the hosted cloud: `https://api.treadstone-ai.dev`, or your self-hosted URL).
- An **API key** for service-to-service calls. Create and scope keys as described in [API Keys & Auth](/docs/api-keys-auth.md); do not paste long-lived secrets into prompts or logs.

## How REST is shaped

### Versioning and health

- **Health** (no version prefix): `GET /health` — quick reachability check; response is small JSON (for example `{"status":"ok"}`). Listed under **System** in [API Reference](/docs/api-reference.md).
- **Control plane API**: paths are under **`/v1/...`**. The base URL in docs is only the host — you concatenate `https://api.example.com` + `/v1/sandboxes`, etc.

Always use **HTTPS** against production.

### Headers you actually need

| Concern | What to send |
|---------|----------------|
| Authentication | `Authorization: Bearer <api_key>` on routes that require auth. |
| JSON bodies | `Content-Type: application/json` with a UTF-8 JSON body. |
| Request shape | Use the HTTP method, path, and JSON fields documented in [API Reference](/docs/api-reference.md) for each operation. |

**Cookies:** the control plane **can** accept a **session cookie** for browser-driven flows. For **automation and server-to-server** integrations, prefer **API keys** only — do not depend on cookie jars in your backend.

### Bodies and responses

- Successful responses are **JSON** unless the route is documented otherwise.
- Errors use a **stable JSON envelope** (`error.code`, `error.message`, `error.status`, etc.). Treat 4xx/5xx bodies as structured data, not plain text. Full shape and codes: [Error Reference](/docs/error-reference.md).

### Control plane vs data plane (REST view)

This is the same split as at the top of the page, in table form:

| | Control plane | Data plane |
|---|----------------|------------|
| **What you are calling** | The Treadstone platform | A **sandbox’s internal HTTP server** (via reverse proxy) |
| **Typical paths** | `/v1/auth/*`, `/v1/sandboxes`, `/v1/usage`, … | `urls.proxy` … **`/proxy/{path}`** — `{path}` is forwarded inside the container |
| **Auth** | `Authorization: Bearer` and/or browser session where applicable | **API keys only**; session cookies do not apply. Narrow keys with `data_plane` scope when possible ([API Keys & Auth](/docs/api-keys-auth.md)). |

Do **not** guess `urls.proxy`, `open_link`, or `web_url` — take them from API responses.

### Discovering the contract

The server exposes **OpenAPI** at **`/openapi.json`** (public, code-first spec). On the hosted control plane, open **[https://api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs)** for **Swagger UI** — browse and try the same routes interactively. Use the JSON spec to generate clients or to inspect schemas when something is ambiguous. The hosted product’s public routes match what the Python SDK is generated from.

## Read Next

- [API Reference](/docs/api-reference.md)
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP servers behind `urls.proxy`
- [Error Reference](/docs/error-reference.md)
- [Python SDK Guide](/docs/python-sdk-guide.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
