# Sandbox Lifecycle

A sandbox moves through a simple set of states: it is created and starts running, you can stop and restart it as needed, and eventually you delete it. Each state transition is one command or API call.

```
create → running → stop → stopped → start → running → … → delete
```

A sandbox only consumes [Compute Units](/docs/usage-limits.md) while it is in the **running** state.

## In the Console

On the Sandboxes page, each row includes a Lifecycle column: **auto-stop** is how long the sandbox can stay running before an idle stop (matches `auto_stop_interval`); **auto-del** is optional deletion after stop (matches `auto_delete_interval`; shown as a dash when disabled).

![Sandboxes table: Lifecycle column with auto-stop and auto-del](/docs/images/sandboxes-lifecycle-column.png)

## Create

### CLI

```bash
# See available templates, then create
$ treadstone --json templates list
$ treadstone --json sandboxes create \
  --template aio-sandbox-tiny \
  --name demo \
  --auto-stop-interval 600
```

```json
{
  "id": "sb_3kx9m2p",
  "name": "demo",
  "template": "aio-sandbox-tiny",
  "status": "running",
  "auto_stop_interval": 600,
  "auto_delete_interval": -1,
  "urls": {
    "proxy": "https://sb_3kx9m2p.proxy.treadstone-ai.dev",
    "web": "https://sb_3kx9m2p.web.treadstone-ai.dev"
  }
}
```

### REST API

```bash
$ curl -sS -X POST https://api.treadstone-ai.dev/v1/sandboxes \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template": "aio-sandbox-tiny", "name": "demo", "auto_stop_interval": 600}'
```

### Python SDK

```python
from treadstone_sdk.api.sandboxes import sandboxes_create_sandbox
from treadstone_sdk.models.create_sandbox_request import CreateSandboxRequest

sandbox = sandboxes_create_sandbox.sync(
    client=client,
    body=CreateSandboxRequest(
        template="aio-sandbox-tiny",
        name="demo",
        auto_stop_interval=600,
    ),
)
print(sandbox.id)         # save this — used in every follow-up call
print(sandbox.urls.proxy) # data-plane entry point
```

Save `id` from the create response. Every subsequent operation uses it, not `name`.

## List & Inspect

### CLI

```bash
$ treadstone --json sandboxes list
$ treadstone --json sandboxes get SANDBOX_ID
```

```json
{
  "id": "sb_3kx9m2p",
  "name": "demo",
  "status": "running",
  "started_at": "2026-03-31T10:00:15+00:00",
  "stopped_at": null
}
```

### REST API

```bash
# List all sandboxes
$ curl -sS https://api.treadstone-ai.dev/v1/sandboxes \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"

# Get one sandbox
$ curl -sS https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python SDK

```python
from treadstone_sdk.api.sandboxes import sandboxes_list_sandboxes, sandboxes_get_sandbox

sandboxes = sandboxes_list_sandboxes.sync(client=client)
sandbox = sandboxes_get_sandbox.sync(sandbox_id="sb_3kx9m2p", client=client)
print(sandbox.status)
```

## Stop & Start

Stopping a sandbox releases compute resources without deleting the sandbox or its state. Starting it again resumes from the same configuration.

### CLI

```bash
$ treadstone sandboxes stop SANDBOX_ID
$ treadstone sandboxes start SANDBOX_ID
```

### REST API

```bash
$ curl -sS -X POST https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/stop \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"

$ curl -sS -X POST https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/start \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python SDK

```python
from treadstone_sdk.api.sandboxes import sandboxes_stop_sandbox, sandboxes_start_sandbox

sandboxes_stop_sandbox.sync(sandbox_id="sb_3kx9m2p", client=client)
sandboxes_start_sandbox.sync(sandbox_id="sb_3kx9m2p", client=client)
```

`auto_stop_interval` does the same thing automatically after the specified seconds of inactivity — set it at create time so the sandbox stops itself if you forget.

## Delete

Deleting permanently removes the sandbox and releases all resources. A stopped sandbox is not deleted unless you delete it explicitly or `auto_delete_interval` fires.

### CLI

```bash
$ treadstone sandboxes delete SANDBOX_ID
```

### REST API

```bash
$ curl -sS -X DELETE https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python SDK

```python
from treadstone_sdk.api.sandboxes import sandboxes_delete_sandbox

sandboxes_delete_sandbox.sync(sandbox_id="sb_3kx9m2p", client=client)
```

Set `auto_delete_interval` at create time to have the platform delete automatically after the sandbox has been stopped for that many seconds. Use `-1` (the default) to disable auto-delete.

## Key Fields

- `template` — the runtime size to use. Must be one of the names from `templates list`. Your plan determines which templates are available.
- `name` — a human label. Optional. Do not use it for programmatic access; use `id`.
- `auto_stop_interval` — seconds of inactivity before the platform stops the sandbox automatically. `0` means never auto-stop.
- `auto_delete_interval` — seconds after stop before the sandbox is permanently deleted. `-1` disables auto-delete.
- `persist` and `storage_size` — attach a persistent volume that survives restarts. Only needed when the sandbox must retain data. `storage_size` is invalid without `persist`.

## Common Failures

- `template_not_found` — run `templates list` and retry with a name from that output.
- `sandbox_name_conflict` — pick another name or omit `--name` to let the platform generate one.
- `compute_quota_exceeded` — check [Usage & Limits](/docs/usage-limits.md).
- `concurrent_limit_exceeded` — stop another running sandbox before starting a new one.
- `sandbox_not_found` — verify the `id`; `name` is not accepted here.

## Read Next

- [Using the data plane](/docs/data-plane.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Usage & Limits](/docs/usage-limits.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
