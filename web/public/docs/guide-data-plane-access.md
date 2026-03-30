# Data Plane Access

## What this page is for

Explain how to send traffic into a sandbox without confusing control-plane and data-plane rules.

## Use this when

- You need proxy access to a running sandbox.
- You want a data-only or selected-sandbox API key.
- You need the real routing contract for `/proxy`.

## Shortest path

```bash
treadstone --json api-keys create --name data-only --no-control-plane --data-plane selected --sandbox-id SANDBOX_ID
curl -i "$BASE_URL/v1/sandboxes/SANDBOX_ID/proxy/" -H "Authorization: Bearer sk-..."
```

## Hard rules

- The proxy path is `/v1/sandboxes/{sandbox_id}/proxy/{path}`.
- Data-plane requests require an API key.
- A saved cookie session is not enough for the proxy path.
- If the API key uses `selected` mode, the current sandbox must be in `sandbox_ids`.

## Create a Data-Only API Key

```bash
treadstone --json api-keys create \
  --name data-only \
  --no-control-plane \
  --data-plane all
```

## Create a Selected-Sandbox API Key

```bash
treadstone --json api-keys create \
  --name scoped-proxy \
  --no-control-plane \
  --data-plane selected \
  --sandbox-id SANDBOX_ID
```

## Send Traffic Through the Proxy

```bash
curl -i "$BASE_URL/v1/sandboxes/SANDBOX_ID/proxy/" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

The platform checks:

- the sandbox exists
- the sandbox belongs to the current user
- the sandbox is ready
- the API key is valid for the requested sandbox

## What the Proxy Is Not

- It is not the sandbox creation API.
- It is not session-cookie friendly.
- It is not a cursor-based resource listing API.

## Common Failures

- `auth_required`: you sent no credential.
- `auth_invalid`: you sent the wrong credential type or an invalid key.
- `forbidden`: the key does not have access to this sandbox.
- `sandbox_not_ready`: the sandbox exists but is not ready yet.
- `sandbox_unreachable`: the platform could not connect to the target runtime.

## For Agents

- Use a dedicated data-plane key when you only need proxy access.
- Use `selected` mode when the workflow should be constrained to one sandbox.
- If the proxy fails, inspect the control-plane sandbox status before retrying blindly.
