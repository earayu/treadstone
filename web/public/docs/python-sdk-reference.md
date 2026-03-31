# Python SDK Reference

The SDK is generated from the OpenAPI schema and mirrors the control-plane API's tag structure. There is no handwritten service layer — endpoint functions map directly to API routes.

## Package Entry Points

| Class | Description |
|-------|-------------|
| `treadstone_sdk.Client` | Unauthenticated client for public routes (health, config). |
| `treadstone_sdk.AuthenticatedClient` | Authenticated client for all protected routes. Accepts `base_url` and `token` (your API key). Use this for almost everything. |

## Layout

```
treadstone_sdk.api.<tag>.<endpoint_module>   # endpoint functions
treadstone_sdk.models.<ModelName>            # request and response models
treadstone_sdk.types                         # shared types and enums
```

## Endpoint Modules

### `treadstone_sdk.api.auth`

| Module | Maps to |
|--------|---------|
| `auth_register` | `POST /v1/auth/register` — create a new account |
| `auth_login` | `POST /v1/auth/login` — start a session |
| `auth_get_user` | `GET /v1/auth/user` — get the current authenticated user |
| `auth_create_api_key` | `POST /v1/auth/api-keys` — create an API key |
| `auth_list_api_keys` | `GET /v1/auth/api-keys` — list API keys |
| `auth_update_api_key` | `PATCH /v1/auth/api-keys/{key_id}` — update key scope or status |
| `auth_delete_api_key` | `DELETE /v1/auth/api-keys/{key_id}` — delete a key |

### `treadstone_sdk.api.sandboxes`

| Module | Maps to |
|--------|---------|
| `sandboxes_create_sandbox` | `POST /v1/sandboxes` — create a sandbox |
| `sandboxes_list_sandboxes` | `GET /v1/sandboxes` — list sandboxes |
| `sandboxes_get_sandbox` | `GET /v1/sandboxes/{sandbox_id}` — get sandbox detail |
| `sandboxes_start_sandbox` | `POST /v1/sandboxes/{sandbox_id}/start` |
| `sandboxes_stop_sandbox` | `POST /v1/sandboxes/{sandbox_id}/stop` |
| `sandboxes_delete_sandbox` | `DELETE /v1/sandboxes/{sandbox_id}` |
| `sandboxes_create_sandbox_web_link` | `POST /v1/sandboxes/{sandbox_id}/web-link` — create or refresh a handoff session |
| `sandboxes_get_sandbox_web_link` | `GET /v1/sandboxes/{sandbox_id}/web-link` — get handoff status |
| `sandboxes_delete_sandbox_web_link` | `DELETE /v1/sandboxes/{sandbox_id}/web-link` — revoke handoff |

### `treadstone_sdk.api.usage`

| Module | Maps to |
|--------|---------|
| `usage_get_usage` | `GET /v1/usage` — summary: compute, storage, limits |
| `usage_get_plan` | `GET /v1/usage/plan` — full plan record |
| `usage_list_compute_sessions` | `GET /v1/usage/sessions` — paginated compute history |
| `usage_list_storage_ledger` | `GET /v1/usage/storage-ledger` — paginated storage history |
| `usage_list_grants` | `GET /v1/usage/grants` — active grants |

## Key Request Models

| Model | Used for |
|-------|----------|
| `CreateSandboxRequest` | `sandboxes_create_sandbox`. Fields: `template` (required), `name`, `label`, `auto_stop_interval`, `auto_delete_interval`, `persist`, `storage_size`. |
| `CreateApiKeyRequest` | `auth_create_api_key`. Fields: `name`, `control_plane`, `data_plane`. |
| `UpdateApiKeyRequest` | `auth_update_api_key`. Fields: `name`, `enabled`, `data_plane`. |

## Key Response Models

| Model | Returned by | Key fields |
|-------|-------------|------------|
| `SandboxResponse` | List operations | `id`, `name`, `status` |
| `SandboxDetailResponse` | `sandboxes_get_sandbox` | `id`, `name`, `status`, `urls.proxy`, `urls.mcp`, `urls.web` |
| `SandboxWebLinkResponse` | `sandboxes_create_sandbox_web_link` | `open_link`, `web_url`, `expires_at` |
| `SandboxWebLinkStatusResponse` | `sandboxes_get_sandbox_web_link` | `enabled`, `web_url`, `expires_at`, `last_used_at` |
| `ApiKeyResponse` | `auth_create_api_key` | Full key value (shown once only), `id`, `name`, scope |
| `ApiKeySummary` | `auth_list_api_keys` | Key metadata without the secret value |
| `UsageSummaryResponse` | `usage_get_usage` | `compute`, `storage`, `limits`, `tier` |

## Call Shapes

Each endpoint module exposes four variants:

| Variant | When to use |
|---------|-------------|
| `sync` | Synchronous call; returns the parsed response model directly. |
| `sync_detailed` | Synchronous call; returns the raw `Response` object with status code and headers. |
| `asyncio` | Async call with `await`; returns the parsed response model. |
| `asyncio_detailed` | Async call with `await`; returns the raw `Response` object. |

> For automation: use the SDK when you want typed models inside Python. Use the REST API docs when you need the shortest contract explanation.
