# API Reference

## Hosted Base URL

- **Control plane**: `https://api.treadstone-ai.dev`
- **Browser handoff and proxy URLs** are returned by the platform. Do not construct them client-side.

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
| `GET/POST/PUT/PATCH/DELETE` | `/v1/sandboxes/{sandbox_id}/proxy/{path}` | Forward a request to the sandbox's internal HTTP server at `{path}`. Requires an API key; session cookies are not accepted. |

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
| `urls.proxy` | The data-plane URL for proxying requests into this sandbox. |
| `urls.web` | The browser entry point, accessible once a web link is enabled. |

### Browser handoff create (`POST /web-link`)

| Field | Description |
|-------|-------------|
| `open_link` | The shareable handoff URL. This is what you send to a human. |
| `web_url` | The canonical browser address for this sandbox. |
| `expires_at` | ISO 8601 timestamp when this handoff session expires. |

### Browser handoff status (`GET /web-link`)

| Field | Description |
|-------|-------------|
| `enabled` | Whether a handoff session is currently active. |
| `web_url` | The canonical browser address for this sandbox. |
| `expires_at` | When the current handoff session expires. |
| `last_used_at` | When the handoff URL was last accessed by a browser. |

### Usage summary (`GET /v1/usage`)

| Field | Description |
|-------|-------------|
| `tier` | The current plan tier name. |
| `compute.total_remaining` | Total compute seconds remaining in the current billing period. |
| `storage.available_gib` | Storage quota remaining across all persistent sandboxes. |
| `limits.allowed_templates` | Template names the current plan permits. |
| `limits.max_concurrent_running` | Maximum number of simultaneously running sandboxes. |
| `limits.max_sandbox_duration_seconds` | Maximum duration allowed for a single sandbox run. |

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
