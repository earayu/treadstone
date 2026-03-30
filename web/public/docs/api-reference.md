# API Reference

The Treadstone REST API is the foundation for the CLI and SDK. All endpoints are prefixed with `/v1`.

The interactive Swagger UI is available at `<base_url>/docs` when the server is running.

## Authentication

Most endpoints require an API key passed as a Bearer token:

```
Authorization: Bearer sk_your_api_key_here
```

Obtain an API key via the web dashboard or CLI:

```bash
treadstone api-keys create --name my-key --save
```

## Base URL

| Environment | Base URL |
|-------------|----------|
| Cloud (default) | `https://api.treadstone-ai.dev` |
| Self-hosted | Your deployment URL |

## Core Endpoints

### Health

```
GET /v1/system/health
```

Returns server status. No authentication required.

```json
{"status": "healthy"}
```

### Authentication

```
POST /v1/auth/register
POST /v1/auth/login
POST /v1/auth/logout
GET  /v1/auth/me
POST /v1/auth/change-password
```

### API Keys

```
POST   /v1/api-keys              Create a new API key
GET    /v1/api-keys              List your API keys
PATCH  /v1/api-keys/{key_id}    Update an API key
DELETE /v1/api-keys/{key_id}    Delete an API key
```

### Sandbox Templates

```
GET /v1/sandbox-templates        List available templates
```

Response:

```json
{
  "items": [
    {
      "name": "aio-sandbox-tiny",
      "cpu": "250m",
      "memory": "512Mi",
      "description": "Lightweight sandbox for scripts and code execution"
    }
  ]
}
```

### Sandboxes

```
POST   /v1/sandboxes              Create a sandbox
GET    /v1/sandboxes              List sandboxes
GET    /v1/sandboxes/{id}         Get a sandbox
POST   /v1/sandboxes/{id}/start   Start a stopped sandbox
POST   /v1/sandboxes/{id}/stop    Stop a running sandbox
DELETE /v1/sandboxes/{id}         Delete a sandbox
```

**Create sandbox request body:**

```json
{
  "name": "my-sandbox",
  "template": "aio-sandbox-tiny",
  "persist": false,
  "storage_size": null,
  "labels": {"env": "dev"}
}
```

**Sandbox object:**

```json
{
  "id": "sb_abc123",
  "name": "my-sandbox",
  "status": "running",
  "template": "aio-sandbox-tiny",
  "created_at": "2026-01-01T00:00:00Z",
  "urls": {
    "web": "https://proxy.treadstone-ai.dev/sb_abc123"
  }
}
```

### Browser Hand-off

```
POST   /v1/sandboxes/{id}/web/enable    Enable browser access
GET    /v1/sandboxes/{id}/web/status    Get browser access status
POST   /v1/sandboxes/{id}/web/disable   Disable browser access
```

`enable` is idempotent — returns the existing URL if already active.

## Error Format

All errors follow a consistent JSON envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Sandbox sb_abc123 not found.",
    "status": 404
  }
}
```

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | `bad_request` | Invalid input |
| 401 | `unauthorized` | Missing or invalid API key |
| 403 | `forbidden` | Insufficient permissions |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Duplicate name or conflicting state |
| 422 | `validation_error` | Request body schema violation |
| 500 | `internal_error` | Server error |

## Rate Limiting

Rate limits are enforced per API key. When exceeded, the API returns `429 Too Many Requests` with a `Retry-After` header.

## Pagination

List endpoints support cursor-based pagination:

```
GET /v1/sandboxes?limit=20&cursor=<next_cursor>
```

Response includes a `next_cursor` field when more results exist:

```json
{
  "items": [...],
  "next_cursor": "eyJpZCI6InNiX3h5eiJ9",
  "total": 100
}
```

## OpenAPI Spec

The full OpenAPI spec can be exported from a running server:

```bash
make gen-openapi           # exports openapi.json to the repo root
```

Or fetched directly:

```
GET /openapi.json
```
