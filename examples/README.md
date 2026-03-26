# End-to-End Examples for Treadstone Control Plane and Sandbox Data Plane

This directory contains runnable examples that connect to a live Treadstone deployment and then call the sandbox data plane behind Treadstone's proxy.

The examples default to the production API base URL:

- Health check: `https://api.treadstone-ai.dev/health`
- Control-plane base URL: `https://api.treadstone-ai.dev`

## What These Examples Show

Treadstone has two layers that users typically combine:

- Control plane: Treadstone auth, API keys, templates, sandbox lifecycle, browser hand-off
- Data plane: the sandbox runtime APIs exposed through `sandbox.urls.proxy`

This directory ships two complete tracks:

- `http_end_to_end.py`: raw HTTP for both control plane and data plane
- `sdk_end_to_end.py`: Treadstone Python SDK for the control plane and the official `agent-sandbox` SDK for the data plane

Both tracks follow the same high-level flow:

1. Check service health
2. Resolve control-plane credentials
3. Create a sandbox
4. Wait until the sandbox is `ready`
5. Create a sandbox-scoped data-plane API key
6. Call representative data-plane APIs
7. Clean up the sandbox and temporary API keys

## Why the Examples Create Two Keys

When the examples need to create credentials for you, they use a least-privilege split:

- Bootstrap control-plane key:
  Used for templates, sandbox create/get/delete, and management APIs. It is created with `control_plane=true` and `data_plane=none`.
- Sandbox-scoped data-plane key:
  Used only for the target sandbox's data-plane APIs. It is created with `control_plane=false` and `data_plane.mode=selected`.

If you already have a Treadstone API key, set `TREADSTONE_API_KEY` or pass `--api-key`. The examples will skip register/login/bootstrap-key creation, but they will still create a sandbox-scoped data-plane key for the demo flow.

## Critical Proxy Rule

This is the most important detail in the whole directory:

- Raw HTTP against the sandbox runtime uses `sandbox.urls.proxy + "/v1/..."`
- The official `agent-sandbox` Python SDK uses `base_url=sandbox.urls.proxy`

Examples:

```text
Raw HTTP:
https://api.treadstone-ai.dev/v1/sandboxes/<sandbox_id>/proxy/v1/sandbox

Official data-plane SDK:
base_url="https://api.treadstone-ai.dev/v1/sandboxes/<sandbox_id>/proxy"
```

Do not add an extra `/v1` when constructing the official data-plane SDK client. That SDK already appends `/v1/...` internally.

## Data-Plane APIs Observed Today

The proxied sandbox OpenAPI currently exposes families such as:

- `sandbox`
- `shell`
- `file`
- `jupyter`
- `nodejs`
- `mcp`
- `browser`
- `code`
- `util`
- `skills`

These examples focus on representative, safe operations that work well in a general sandbox:

- sandbox context
- shell command execution
- file write
- file read
- browser info

## Prerequisites

Run all commands from the repository root.

You can authenticate in one of two ways:

- Preferred for repeat runs:
  Provide `TREADSTONE_API_KEY`
- Account bootstrap flow:
  Provide `TREADSTONE_EMAIL` and `TREADSTONE_PASSWORD`

Shared runtime knobs:

- `TREADSTONE_BASE_URL`
  Default: `https://api.treadstone-ai.dev`
- `TREADSTONE_TEMPLATE`
  Default: `aio-sandbox-tiny`
- `TREADSTONE_EMAIL`
- `TREADSTONE_PASSWORD`
- `TREADSTONE_API_KEY`
- `--keep-sandbox`
- `--keep-keys`

## Example 1: Raw HTTP

This example uses Python `httpx` only. It is useful when you want the most explicit, OpenAPI-shaped flow.

With email/password bootstrap:

```bash
export TREADSTONE_EMAIL="agent@example.com"
export TREADSTONE_PASSWORD="YourPass123!"
uv run --with httpx python examples/http_end_to_end.py
```

With an existing control-plane API key:

```bash
export TREADSTONE_API_KEY="sk_your_control_plane_key"
uv run --with httpx python examples/http_end_to_end.py
```

Keep the sandbox and temporary keys for manual inspection:

```bash
uv run --with httpx python examples/http_end_to_end.py --keep-sandbox --keep-keys
```

## Example 2: SDK Flow

This example uses:

- `treadstone-sdk` for control-plane calls
- `agent-sandbox` for data-plane calls

It still uses raw HTTP for register/login/bootstrap-key creation when `TREADSTONE_API_KEY` is not provided.

With email/password bootstrap:

```bash
export TREADSTONE_EMAIL="agent@example.com"
export TREADSTONE_PASSWORD="YourPass123!"
uv run --with httpx --with treadstone-sdk --with agent-sandbox python examples/sdk_end_to_end.py
```

With an existing control-plane API key:

```bash
export TREADSTONE_API_KEY="sk_your_control_plane_key"
uv run --with httpx --with treadstone-sdk --with agent-sandbox python examples/sdk_end_to_end.py
```

Keep the sandbox and temporary keys for manual inspection:

```bash
uv run --with httpx --with treadstone-sdk --with agent-sandbox python examples/sdk_end_to_end.py --keep-sandbox --keep-keys
```

## What Each Script Actually Calls

`http_end_to_end.py` covers:

- `GET /health`
- `POST /v1/auth/login`
- `POST /v1/auth/register`
- `POST /v1/auth/api-keys`
- `GET /v1/sandbox-templates`
- `POST /v1/sandboxes`
- `GET /v1/sandboxes/{sandbox_id}`
- `DELETE /v1/sandboxes/{sandbox_id}`
- Raw data-plane calls through `sandbox.urls.proxy + "/v1/..."`

`sdk_end_to_end.py` covers:

- `treadstone_sdk.api.system.system_health`
- `treadstone_sdk.api.sandbox_templates.sandbox_templates_list_sandbox_templates`
- `treadstone_sdk.api.sandboxes.sandboxes_create_sandbox`
- `treadstone_sdk.api.sandboxes.sandboxes_get_sandbox`
- `treadstone_sdk.api.sandboxes.sandboxes_delete_sandbox`
- `treadstone_sdk.api.auth.auth_create_api_key`
- `treadstone_sdk.api.auth.auth_delete_api_key`
- `agent_sandbox.Sandbox(...).sandbox.get_context()`
- `agent_sandbox.Sandbox(...).shell.exec_command()`
- `agent_sandbox.Sandbox(...).file.write_file()`
- `agent_sandbox.Sandbox(...).file.read_file()`
- `agent_sandbox.Sandbox(...).browser.get_info()`

## CLI Equivalence

This directory does not ship dedicated CLI example files, but the equivalent control-plane flow is available through the Treadstone CLI:

```bash
treadstone system health
treadstone auth login
treadstone api-keys create --name demo
treadstone templates list
treadstone sandboxes create --template aio-sandbox-tiny --name demo
treadstone sandboxes get <sandbox_id>
treadstone sandboxes delete <sandbox_id>
```

The data-plane portion still uses the sandbox proxy URL returned by `sandboxes get`.
