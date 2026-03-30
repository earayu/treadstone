# Create and Manage Sandboxes

## What this page is for

Show the practical sandbox lifecycle without turning it into a full API encyclopedia.

## Use this when

- You need to choose a template and create a sandbox correctly.
- You need to understand `persist`, labels, auto-stop, or auto-delete.
- You need the right follow-up command after create.

## Shortest path

```bash
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo --label env:dev
treadstone --json sandboxes get SANDBOX_ID
treadstone sandboxes stop SANDBOX_ID
treadstone sandboxes start SANDBOX_ID
treadstone sandboxes delete SANDBOX_ID
```

## Hard rules

- Validate template names against the platform before create.
- Names are lowercase letters, numbers, and hyphens only.
- Labels use `key:value`.
- Persistent storage requires `--persist`; `storage_size` is invalid without it.

## Choose a Template

List templates first:

```bash
treadstone --json templates list
```

The server returns the real template names, resource requests, and allowed storage sizes.

## Create an Ephemeral Sandbox

```bash
treadstone --json sandboxes create \
  --template aio-sandbox-tiny \
  --name demo \
  --label env:dev \
  --auto-stop-interval 15 \
  --auto-delete-interval -1
```

Use ephemeral sandboxes when the workspace does not need to survive stop and restart events.

## Create a Persistent Sandbox

```bash
treadstone --json sandboxes create \
  --template aio-sandbox-small \
  --name dev-box \
  --persist \
  --storage-size 5Gi
```

Use persistent sandboxes when the workspace must survive lifecycle events.

## List and Filter

```bash
treadstone --json sandboxes list
treadstone --json sandboxes list --label env:dev --limit 20 --offset 0
```

The list API uses `limit` and `offset`. It does not use cursors.

## Inspect Current State

```bash
treadstone --json sandboxes get SANDBOX_ID
```

Read the current `status`, not your memory of the create response.

## Start, Stop, Delete

```bash
treadstone sandboxes stop SANDBOX_ID
treadstone sandboxes start SANDBOX_ID
treadstone sandboxes delete SANDBOX_ID
```

## Common Failures

- `template_not_found`: you used a template the server does not expose.
- `sandbox_name_conflict`: the current user already owns that name.
- `email_verification_required`: the user is not verified yet.
- `storage_backend_not_ready`: persistent storage is not available in the cluster.

## For Agents

- Capture `id`, `status`, and `urls.proxy` from create output.
- If the sandbox is persistent, also retain `storage_size` and `persist`.
- When a follow-up step depends on sandbox state, call `get` first.
