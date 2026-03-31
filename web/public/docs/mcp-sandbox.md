# MCP in sandbox

## What this page is for

Expose a **Model Context Protocol (MCP)** server that runs **inside** a Treadstone sandbox to external MCP clients (IDEs, desktop apps, scripts) using the platform’s **data-plane HTTP proxy** and optional **WebSocket proxy**. Treadstone terminates TLS and API-key auth at the edge; traffic is forwarded to the sandbox container’s HTTP listener (typically port **8080**).

## Use this when

- You run an MCP server in the sandbox that listens on a path such as **`/mcp`** (or another path you choose).
- Your client speaks **HTTP with SSE** and/or **WebSocket** MCP transports.
- You need a **stable, documented URL shape** instead of inventing hostnames.

## Shortest path

1. Create a sandbox and wait until **`status` is `ready`** ([Sandbox Lifecycle](/docs/sandbox-lifecycle.md)).
2. Call **`GET /v1/sandboxes/{sandbox_id}`** and read **`urls.proxy`** from the response (do not construct this URL by hand).
3. Append your MCP path, usually **`mcp`**, so the full data-plane URL is:

   `https://<api-host>/v1/sandboxes/{sandbox_id}/proxy/mcp`

4. Send requests with **`Authorization: Bearer sk-…`** using an API key that has **data-plane** access ([API Keys & Auth](/docs/api-keys-auth.md)).

For the full contract (query forwarding, WebSocket, `?token=`, subdomain browser URLs), see the **Proxy** section in [API Reference](/docs/api-reference.md).

## Hard rules

- **Data plane accepts API keys only** — not browser session cookies. Narrow keys with **selected sandbox** scope when possible.
- **Never guess** `urls.proxy`, `urls.web`, or `open_link` — always take them from API responses.
- **Query strings** are forwarded unchanged (needed for MCP SSE session parameters such as `?sessionId=…`).
- **WebSocket**: same path pattern; use `Authorization: Bearer sk-…`, or **`?token=sk-…`** if the client cannot set WebSocket headers (the `token` query param is stripped before traffic reaches the sandbox).
- **Subdomain URLs** (`https://sandbox-{id}.<domain>/…`) are for **browser** flows with cookie auth; for MCP automation, prefer the **`urls.proxy`** form above.

## How it fits the platform

| Piece | Role |
| --- | --- |
| Control plane | Create sandboxes, issue API keys, read `urls.proxy` / `urls.web` |
| Data plane (`/v1/sandboxes/{id}/proxy/{path}`) | Reverse proxy into the sandbox; your MCP server sees `{path}` and the query string |
| Sandbox runtime | Runs your MCP process bound to the container HTTP port (default **8080** in sandbox templates) |

Self-hosted operators: wildcard DNS, Ingress, and TLS for sandbox subdomains are documented in the repository at **`deploy/README.md`** (section *Exposing the Sandbox MCP Endpoint Publicly*).

## Read next

- [API Reference](/docs/api-reference.md) — Proxy routes, MCP subsection, error shape
- [REST API Guide](/docs/rest-api-guide.md) — Control plane vs data plane
- [API Keys & Auth](/docs/api-keys-auth.md) — Scoping keys for data-plane access

## For agents

- **Stable pattern**: `{control_plane_base}/v1/sandboxes/{sandbox_id}/proxy/{mcp_path}` where `mcp_path` is often literally `mcp`.
- **Auth header**: `Authorization: Bearer <sk-…>` on every request / WebSocket handshake.
- **Discover URLs** from `GET /v1/sandboxes/{id}` → `urls.proxy`; append `/mcp` (or the path your server uses).
- **Do not** use subdomain `urls.web` for unattended MCP unless the client supports cookie / bootstrap flows documented in [API Reference](/docs/api-reference.md).
