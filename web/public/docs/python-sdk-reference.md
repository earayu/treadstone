# Python SDK Reference

## Package Entry Points

- `treadstone_sdk.Client`
- `treadstone_sdk.AuthenticatedClient`

## Layout

- Endpoint modules: `treadstone_sdk.api.<tag>`
- Models: `treadstone_sdk.models`
- Enums and helper types: `treadstone_sdk.types`, `treadstone_sdk.models`

The SDK is generated from the OpenAPI schema. It mirrors the API tags and route groups.

## Useful Endpoint Modules

### `treadstone_sdk.api.auth`

- `auth_register`
- `auth_login`
- `auth_get_user`
- `auth_create_api_key`
- `auth_list_api_keys`
- `auth_update_api_key`
- `auth_delete_api_key`

### `treadstone_sdk.api.sandboxes`

- `sandboxes_create_sandbox`
- `sandboxes_list_sandboxes`
- `sandboxes_get_sandbox`
- `sandboxes_start_sandbox`
- `sandboxes_stop_sandbox`
- `sandboxes_delete_sandbox`
- `sandboxes_create_sandbox_web_link`
- `sandboxes_get_sandbox_web_link`
- `sandboxes_delete_sandbox_web_link`

### `treadstone_sdk.api.usage`

- `usage_get_usage`
- `usage_get_plan`
- `usage_list_compute_sessions`
- `usage_list_storage_ledger`
- `usage_list_grants`

## Common Request Models

- `CreateSandboxRequest`
- `CreateApiKeyRequest`
- `UpdateApiKeyRequest`

## Common Response Models

- `SandboxResponse`
- `SandboxDetailResponse`
- `SandboxWebLinkResponse`
- `SandboxWebLinkStatusResponse`
- `ApiKeyResponse`
- `ApiKeySummary`
- `UsageSummaryResponse`

## Call Shapes

Each generated endpoint module exposes:

- `sync`
- `sync_detailed`
- `asyncio`
- `asyncio_detailed`

> For automation: use the SDK when you want typed models inside Python. Use the REST API docs when you need the shortest contract explanation.
