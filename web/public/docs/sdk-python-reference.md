# Python SDK Reference

## What this page is for

Map the generated Python SDK layout to the API it wraps.

## Use this when

- You need the real import paths.
- You need to know how generated endpoint modules are named.
- You want sync and async call-shape reminders.

## Shortest path

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest
```

## Hard rules

- The package exports `Client` and `AuthenticatedClient`.
- Endpoint modules live under `treadstone_sdk.api.<tag>`.
- Models live under `treadstone_sdk.models`.
- The SDK mirrors the OpenAPI tags. It is not a handwritten service layer.

## Package Entry Points

- `treadstone_sdk.Client`
- `treadstone_sdk.AuthenticatedClient`

## Useful Endpoint Modules

### `treadstone_sdk.api.auth`

- `auth_get_user`
- `auth_register`
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

### `treadstone_sdk.api.system`

- `system_health`

### `treadstone_sdk.api.config`

- `config_get_config`

### `treadstone_sdk.api.usage`

Use the `usage` tag modules for plan, summary, sessions, storage ledger, and grants.

## Call Shapes

Every generated endpoint module exposes:

- `sync`
- `sync_detailed`
- `asyncio`
- `asyncio_detailed`

## Request Models

Common request models:

- `CreateSandboxRequest`
- `CreateApiKeyRequest`
- `UpdateApiKeyRequest`
- `UpdatePlanRequest`

## Response Models

Common response models:

- `SandboxResponse`
- `SandboxDetailResponse`
- `SandboxWebLinkResponse`
- `SandboxWebLinkStatusResponse`
- `ApiKeyResponse`
- `UserDetailResponse`

## For Agents

- Prefer the SDK when you already live in Python and want type-safe request models.
- Prefer REST when you need the shortest possible contract explanation.
