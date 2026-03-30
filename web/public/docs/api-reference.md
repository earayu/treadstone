# API Reference

## What this page is for

Document the Treadstone-owned public API contract: route groups, auth model, proxy path, pagination, and error semantics.

## Use this when

- You need exact route prefixes.
- You need to know whether a request belongs to the control plane or the data plane.
- You need contract-level truth before writing code.

## Shortest path

```text
GET  /health
GET  /v1/config
GET  /v1/auth/user
GET  /v1/sandbox-templates
POST /v1/sandboxes
POST /v1/sandboxes/{sandbox_id}/web-link
GET  /v1/usage
GET  /v1/admin/stats
```

Obtain an API key via the web console or CLI:

## Hard rules

- Health is `/health`, not `/v1/system/health`.
- Current user is `/v1/auth/user`, not `/v1/auth/me`.
- API keys live under `/v1/auth/api-keys`.
- Browser hand-off uses `/v1/sandboxes/{sandbox_id}/web-link`.
- Paginated list routes use `limit` and `offset`.

## Auth Model

### Control plane

Accepted credentials:

- session cookie
- API key

Examples:

- `/v1/auth/*`
- `/v1/sandboxes/*`
- `/v1/usage/*`
- `/v1/admin/*`

### Data plane

Accepted credential:

- API key only

Example:

- `/v1/sandboxes/{sandbox_id}/proxy/{path}`

## Route Map

### System

- `GET /health`

### Config

- `GET /v1/config`

### Auth

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET /v1/auth/user`
- `POST /v1/auth/change-password`
- `POST /v1/auth/verification/request`
- `POST /v1/auth/verification/confirm`
- `GET /v1/auth/users`
- `DELETE /v1/auth/users/{user_id}`
- `POST /v1/auth/api-keys`
- `GET /v1/auth/api-keys`
- `PATCH /v1/auth/api-keys/{key_id}`
- `DELETE /v1/auth/api-keys/{key_id}`

### Templates

- `GET /v1/sandbox-templates`

### Sandboxes

- `POST /v1/sandboxes`
- `GET /v1/sandboxes`
- `GET /v1/sandboxes/{sandbox_id}`
- `POST /v1/sandboxes/{sandbox_id}/start`
- `POST /v1/sandboxes/{sandbox_id}/stop`
- `DELETE /v1/sandboxes/{sandbox_id}`
- `POST /v1/sandboxes/{sandbox_id}/web-link`
- `GET /v1/sandboxes/{sandbox_id}/web-link`
- `DELETE /v1/sandboxes/{sandbox_id}/web-link`

### Proxy

- `GET|POST|PUT|PATCH|DELETE /v1/sandboxes/{sandbox_id}/proxy/{path}`

### Usage

- `GET /v1/usage`
- `GET /v1/usage/plan`
- `GET /v1/usage/sessions`
- `GET /v1/usage/storage-ledger`
- `GET /v1/usage/grants`

### Admin

- `GET /v1/admin/stats`
- `GET /v1/admin/tier-templates`
- `PATCH /v1/admin/tier-templates/{tier_name}`
- `GET /v1/admin/users/lookup-by-email`
- `POST /v1/admin/users/resolve-emails`
- `GET /v1/admin/users/{user_id}/usage`
- `PATCH /v1/admin/users/{user_id}/plan`
- `POST /v1/admin/users/{user_id}/compute-grants`
- `POST /v1/admin/users/{user_id}/storage-grants`
- `POST /v1/admin/compute-grants/batch`
- `POST /v1/admin/storage-grants/batch`

## Pagination

List routes use:

- `limit`
- `offset`

Examples:

- `/v1/sandboxes?limit=20&offset=0`
- `/v1/usage/sessions?limit=20&offset=0`
- `/v1/usage/storage-ledger?limit=20&offset=0`

## Error Envelope

All API errors use:

```json
{
  "error": {
    "code": "snake_case_code",
    "message": "Human-readable detail.",
    "status": 409
  }
}
```

## Browser Handoff Contract

Create:

```text
POST /v1/sandboxes/{sandbox_id}/web-link
```

Response fields:

- `web_url`
- `open_link`
- `expires_at`

Status:

```text
GET /v1/sandboxes/{sandbox_id}/web-link
```

Response fields:

- `web_url`
- `enabled`
- `expires_at`
- `last_used_at`

## For Agents

- Use this page for route truth and auth truth.
- Use the quickstarts for example flow.
- Use [`error-reference.md`](/docs/error-reference.md) when you need recovery advice, not just error names.
