# API Reference

## Hosted Base URL

- **Control plane**: `https://api.treadstone-ai.dev`
- **Interactive REST docs (Swagger UI)**: [https://api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs) — documents **control-plane** routes and **data-plane** proxy routes. Sandbox HTTP APIs are merged under `/v1/sandboxes/{sandbox_id}/proxy/...` (tagged like `Sandbox: …` in the UI) so you can explore REST shapes for traffic into a sandbox; call them with a real `sandbox_id` and `Authorization: Bearer <api_key>`.
- **OpenAPI JSON**: `https://api.treadstone-ai.dev/openapi.json` (same as `GET /openapi.json` on the control plane host) — same merged document as Swagger.
- **Browser handoff and proxy URLs** are returned by the platform. Do not construct them client-side.

**SDK generation:** The Python SDK and repo `make gen-openapi` output use a **public** OpenAPI export **without** the merged sandbox-runtime paths. Use the hosted `/docs` or `/openapi.json` when you need schemas for operations under `/v1/sandboxes/{sandbox_id}/proxy/...`.

## Auth Surfaces

| Surface | Routes | Accepted credentials |
| --- | --- | --- |
| Control plane | `/v1/auth/*`, `/v1/sandbox-templates`, `/v1/sandboxes/*`, `/v1/usage/*` | session cookie or API key |
| Data plane | `/v1/sandboxes/{sandbox_id}/proxy/{path}` | API key only |

## Routes

### System

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/health` | Returns `{"status":"ok"}` when the API is reachable. Use this to verify connectivity before other calls. |

### Config

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/v1/config` | Returns public server configuration — registration mode, feature flags, and platform metadata. |

### Auth

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/v1/auth/register` | Create a new account. Body: `email`, `password`. |
| `POST` | `/v1/auth/login` | Start a session with email and password. Sets a session cookie on success. |
| `POST` | `/v1/auth/logout` | Invalidate the current session cookie. |
| `GET` | `/v1/auth/user` | Return the authenticated user record. Use this to verify credentials and check email verification status. There is no `/v1/auth/me`. |
| `POST` | `/v1/auth/change-password` | Change the password for the authenticated account. |
| `POST` | `/v1/auth/verification/request` | Request a new email verification link for the current account. |
| `POST` | `/v1/auth/verification/confirm` | Confirm email verification with the token from the verification email. |
| `POST` | `/v1/auth/api-keys` | Create an API key with the specified name and scope. The full key value is returned once only. |
| `GET` | `/v1/auth/api-keys` | List all API keys for the authenticated account with their scope and status. |
| `PATCH` | `/v1/auth/api-keys/{key_id}` | Update an API key: rename, enable, disable, or change scope. |
| `DELETE` | `/v1/auth/api-keys/{key_id}` | Permanently delete an API key. |

### Templates

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/v1/sandbox-templates` | List the sandbox templates available to the current account's plan. Use this to discover valid values for the `template` field when creating a sandbox. |

### Sandboxes

| Method | Path | What it does |
|--------|------|--------------|
| `POST` | `/v1/sandboxes` | Create a sandbox. Required body field: `template`. Optional: `name`, `label`, `auto_stop_interval`, `auto_delete_interval`, `persist`, `storage_size`. Returns `202 Accepted` with the sandbox record immediately. |
| `GET` | `/v1/sandboxes` | List sandboxes for the current account. Supports `limit`, `offset`, and label filter query params. |
| `GET` | `/v1/sandboxes/{sandbox_id}` | Get the full detail record for one sandbox including current status and URLs. |
| `POST` | `/v1/sandboxes/{sandbox_id}/start` | Start a stopped sandbox. |
| `POST` | `/v1/sandboxes/{sandbox_id}/stop` | Stop a running sandbox without deleting it. |
| `DELETE` | `/v1/sandboxes/{sandbox_id}` | Delete a sandbox and release all its resources. |
| `POST` | `/v1/sandboxes/{sandbox_id}/web-link` | Create or refresh a browser handoff session. Returns `open_link`, `web_url`, and `expires_at`. If a session is already active, returns the current live link. |
| `GET` | `/v1/sandboxes/{sandbox_id}/web-link` | Get the current browser handoff status. Returns `enabled`, `web_url`, `expires_at`, `last_used_at`. Does not return `open_link`. |
| `DELETE` | `/v1/sandboxes/{sandbox_id}/web-link` | Revoke the current browser handoff link immediately. |

### Proxy

| Method | Path | What it does |
|--------|------|--------------|
| `GET/POST/PUT/PATCH/DELETE` | `/v1/sandboxes/{sandbox_id}/proxy/{path}` | Forward a request to the sandbox's internal HTTP server at `{path}`. Requires an API key; session cookies are not accepted. Query strings are forwarded to the sandbox unchanged. |
| `WebSocket` | `/v1/sandboxes/{sandbox_id}/proxy/{path}` | Upgrade to a WebSocket connection proxied to the sandbox. Pass the API key as `Authorization: Bearer sk-…` header, or as a `?token=sk-…` query param for clients that cannot set WebSocket headers. |

#### Using the Proxy with MCP

The data-plane proxy is the recommended way to connect MCP clients (Cursor, Claude Desktop, scripts) to an MCP server running inside a sandbox.

**HTTP / SSE transport** — use the standard HTTP proxy path:

```
GET https://api.treadstone-ai.dev/v1/sandboxes/{id}/proxy/mcp
Authorization: Bearer sk-…
```

SSE session parameters (e.g. `?sessionId=abc`) are forwarded to the sandbox unchanged.

**WebSocket transport** — use the same path with a WebSocket upgrade:

```
wss://api.treadstone-ai.dev/v1/sandboxes/{id}/proxy/mcp
Authorization: Bearer sk-…
```

**Browser / subdomain access** — For a human or browser session in the workspace UI, use **`urls.web`** from the API (host and path come from server config; do not hard-code). Authentication is via Console session cookie or a shareable **`open_link`** from `POST /v1/sandboxes/{id}/web-link`. That surface is different from **`urls.mcp`**: MCP automation should use the proxy URL and API keys, not `urls.web`, unless your client explicitly supports the browser flow.

### Sandbox runtime APIs (merged data plane)

The route tables **above** list **Treadstone control-plane** endpoints and **one generic** proxy row. They do **not** enumerate every HTTP route that runs **inside** the sandbox.

Those workloads are described by a separate OpenAPI document bundled with the server (`scripts/sandbox_openapi_base.json` in the repository). At runtime, Treadstone **merges** it under:

`/v1/sandboxes/{sandbox_id}/proxy` + **`<path from the sandbox spec>`**

So a sandbox route like `/v1/shell/exec` becomes:

`/v1/sandboxes/{sandbox_id}/proxy/v1/shell/exec`

In [Swagger UI](https://api.treadstone-ai.dev/docs) they appear under tags **`Sandbox: <name>`** (for example `Sandbox: shell`, `Sandbox: file`, `Sandbox: browser`) — the same operations as in `scripts/sandbox_openapi_base.json`, with `sandbox_id` injected. Auth is **`Authorization: Bearer <api_key>`** with data-plane access, same as the generic proxy.

#### Sandbox runtime paths (from `sandbox_openapi_base.json`)

The tables below list **every path** in the bundled sandbox OpenAPI spec. Each row is the suffix after `/v1/sandboxes/{sandbox_id}/proxy`. If the spec changes, update this section from the same file or use **Swagger** / **`openapi.json`** as the source of truth.

##### `browser` — in-VM browser automation

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/browser/actions` | Execute action |
| `POST` | `/v1/browser/config` | Set config |
| `GET` | `/v1/browser/info` | Get browser info |
| `GET` | `/v1/browser/screenshot` | Take screenshot |

##### `code` — Python execution

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/code/execute` | Execute code |
| `GET` | `/v1/code/info` | Code info |

##### `file` — filesystem

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `GET` | `/v1/file/download` | Download file |
| `POST` | `/v1/file/find` | Find files |
| `POST` | `/v1/file/list` | List path |
| `POST` | `/v1/file/read` | Read file |
| `POST` | `/v1/file/replace` | Replace in file |
| `POST` | `/v1/file/search` | Search in file |
| `POST` | `/v1/file/str_replace_editor` | Str replace editor |
| `POST` | `/v1/file/upload` | Upload file |
| `POST` | `/v1/file/write` | Write file |

##### `jupyter`

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/jupyter/execute` | Execute Jupyter code |
| `GET` | `/v1/jupyter/info` | Jupyter info |
| `GET` | `/v1/jupyter/sessions` | List sessions |
| `DELETE` | `/v1/jupyter/sessions` | Cleanup all sessions |
| `POST` | `/v1/jupyter/sessions/create` | Create Jupyter session |
| `DELETE` | `/v1/jupyter/sessions/{session_id}` | Cleanup session |

##### `mcp`

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `GET` | `/v1/mcp/servers` | List MCP servers |
| `GET` | `/v1/mcp/{server_name}/tools` | List MCP tools |
| `POST` | `/v1/mcp/{server_name}/tools/{tool_name}` | Execute MCP tool |

##### `nodejs` — Node execution

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/nodejs/execute` | Execute Node.js code |
| `GET` | `/v1/nodejs/info` | Node.js info |

##### `sandbox` — environment context

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `GET` | `/v1/sandbox` | Get sandbox context |
| `GET` | `/v1/sandbox/packages/python` | Python packages |
| `GET` | `/v1/sandbox/packages/nodejs` | Node.js packages |

##### `shell`

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/shell/exec` | Exec command (optional SSE via `Accept: text/event-stream`) |
| `POST` | `/v1/shell/view` | View shell |
| `POST` | `/v1/shell/wait` | Wait for process |
| `POST` | `/v1/shell/write` | Write to process |
| `POST` | `/v1/shell/kill` | Kill process |
| `POST` | `/v1/shell/sessions/create` | Create session |
| `GET` | `/v1/shell/terminal-url` | Get terminal URL |
| `GET` | `/v1/shell/sessions` | List sessions |
| `DELETE` | `/v1/shell/sessions` | Cleanup all sessions |
| `DELETE` | `/v1/shell/sessions/{session_id}` | Cleanup session |

##### `skills`

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `DELETE` | `/v1/skills` | Clear skills |
| `GET` | `/v1/skills/metadatas` | List skills metadata |
| `POST` | `/v1/skills/register` | Register skills |
| `DELETE` | `/v1/skills/{name}` | Delete skill |
| `GET` | `/v1/skills/{name}/content` | Get skill content |

##### `util`

| Method | Path suffix | Summary |
|--------|-------------|---------|
| `POST` | `/v1/util/convert_to_markdown` | Convert to Markdown |

Request and response schemas for these operations are in **`sandbox_openapi_base.json`** and in the hosted **Swagger** / **`openapi.json`** — not duplicated here.

### Usage

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/v1/usage` | Summary: compute remaining, storage available, current concurrency, and plan limits. |
| `GET` | `/v1/usage/plan` | Full plan record including the template names your plan allows and storage tier. |
| `GET` | `/v1/usage/sessions` | Paginated history of past compute sessions. |
| `GET` | `/v1/usage/storage-ledger` | Paginated storage usage history. |
| `GET` | `/v1/usage/grants` | Active compute and storage grants applied to the account. |

## Response Fields You Will Reuse

### Sandbox (create or get)

| Field | Description |
|-------|-------------|
| `id` | The machine identifier for this sandbox. Use it for every subsequent operation. |
| `name` | The human label. Not a stable identifier; use `id` for programmatic access. |
| `status` | Current lifecycle state: `creating`, `stopped`, `running`, `error`, etc. |
| `urls.proxy` | The data-plane base for HTTP/WebSocket into this sandbox (`…/v1/sandboxes/{id}/proxy`). |
| `urls.mcp` | The MCP endpoint URL (`urls.proxy` + `/mcp`). Prefer this for MCP clients instead of constructing paths. |
| `urls.web` | Browser workspace entry (subdomain URL when configured; may include a handoff token when a web link is active). |

### Browser handoff create (`POST /web-link`)

| Field | Description |
|-------|-------------|
| `open_link` | Shareable handoff URL with an embedded token. Anyone with the link can open the workspace without a Treadstone login. |
| `web_url` | Canonical browser address for the sandbox. Opening it requires an existing Console (account) session — not a substitute for sharing `open_link`. |
| `expires_at` | ISO 8601 timestamp when this handoff session expires. |

### Browser handoff status (`GET /web-link`)

| Field | Description |
|-------|-------------|
| `enabled` | Whether a handoff session is currently active. |
| `web_url` | Canonical browser address; access assumes a logged-in account unless you already hold a sandbox cookie from `open_link`. |
| `expires_at` | When the current handoff session expires. |
| `last_used_at` | When the handoff URL was last accessed by a browser. |

### Usage summary (`GET /v1/usage`)

| Field | Description |
|-------|-------------|
| `tier` | The current plan tier name. |
| `compute.total_remaining` | **CU-hours** left in the current billing period (same unit as `compute.unit`, usually `CU-hours`). Monthly pool and bonus credits are reflected here. |
| `storage.available_gib` | Storage quota remaining across all persistent sandboxes. |
| `limits.allowed_templates` | Template names the current plan permits. |
| `limits.max_concurrent_running` | Maximum number of simultaneously running sandboxes. |
| `limits.current_running` | How many sandboxes are **running** right now. |
| `limits.max_sandbox_duration_seconds` | Upper bound for `auto_stop_interval` (and similar) in seconds; `0` means unlimited where the API allows. |

## Pagination

List routes accept `limit` and `offset` query params:

- `/v1/sandboxes?limit=20&offset=0`
- `/v1/usage/sessions?limit=20&offset=0`
- `/v1/usage/storage-ledger?limit=20&offset=0`

## Error Envelope

```json
{
  "error": {
    "code": "snake_case_code",
    "message": "Human-readable detail.",
    "status": 409
  }
}
```

Build retry and recovery logic around `error.code`. See [Error Reference](/docs/error-reference.md) for the full code list.

## Notes

- Browser login and OAuth helper routes exist for the Console and CLI but are not the recommended integration surface for third-party services.
- Admin routes exist in the product but are intentionally omitted from this public reference.

> For automation: treat `sandbox_id`, auth mode, pagination params, and error codes as stable contract data. Do not infer them from page copy or browser behavior.
