# API Reference

## Hosted Base URL

- Control plane: `https://api.treadstone-ai.dev`
- Browser entry URLs are returned by the platform. Do not construct them.

## Auth Surfaces

| Surface | Routes | Accepted credentials |
| --- | --- | --- |
| Control plane | `/v1/auth/*`, `/v1/sandbox-templates`, `/v1/sandboxes/*`, `/v1/usage/*` | session cookie or API key |
| Data plane | `/v1/sandboxes/{sandbox_id}/proxy/{path}` | API key only |

## Route Map

### System

- `GET /health`

### Public config

- `GET /v1/config`

### Auth

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `GET /v1/auth/user`
- `POST /v1/auth/change-password`
- `POST /v1/auth/verification/request`
- `POST /v1/auth/verification/confirm`
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

## Response Shapes You Will Reuse

### Sandbox create or get

- `id`
- `name`
- `status`
- `urls.proxy`
- `urls.web`

### Browser handoff create

- `web_url`
- `open_link`
- `expires_at`

### Browser handoff status

- `web_url`
- `enabled`
- `expires_at`
- `last_used_at`

### Usage summary

- `tier`
- `compute.total_remaining`
- `storage.available_gib`
- `limits.allowed_templates`
- `limits.max_concurrent_running`
- `limits.max_sandbox_duration_seconds`

## Pagination

List routes use `limit` and `offset` query params.

Examples:

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

## Notes

- `GET /v1/auth/user` is the current-user endpoint. There is no `/v1/auth/me`.
- Browser login and OAuth helper routes exist for the web app and CLI, but they are not the recommended integration surface for third-party services.
- Admin routes exist in the product, but they are intentionally omitted from this hosted end-user public reference.

> For automation: treat `sandbox_id`, auth mode, pagination, and error codes as contract data. Do not infer them from page copy or browser behavior.
