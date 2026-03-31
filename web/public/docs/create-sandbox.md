# Create a Sandbox

A sandbox is an isolated runtime environment. You pick a template, set its lifecycle rules, and optionally attach persistent storage. The platform returns a `sandbox_id` immediately — that identifier is what every follow-up command uses.

## Create One

```bash
treadstone --json templates list
treadstone --json sandboxes create \
  --template aio-sandbox-tiny \
  --name demo \
  --label project:docs \
  --auto-stop-interval 60 \
  --auto-delete-interval -1
```

If you need a sandbox that retains data across restarts, add `--persist --storage-size 5Gi`.

## Understand The Fields

- `template` — the runtime shape to use. Must come from `templates list` or `/v1/sandbox-templates`. Your plan determines which templates are available.
- `name` — a human label. Optional and unique only within your account. Do not rely on it for programmatic access; use `id`.
- `label` — repeatable `key:value` metadata you can filter on later with `sandboxes list`.
- `auto-stop-interval` — minutes of inactivity before the platform stops the sandbox automatically. `0` means never auto-stop.
- `auto-delete-interval` — minutes after stop before the sandbox is permanently deleted. `-1` disables auto-delete, leaving the sandbox in a stopped state until you delete it manually.
- `persist` and `storage-size` — attach a persistent volume that survives restarts. Only set this when the sandbox actually needs to retain data. `storage-size` is invalid without `--persist`.

## Save These From The Response

- `id` — the machine identifier. Every follow-up action (start, stop, browser handoff, delete) uses this.
- `status` — the current lifecycle state.
- `urls.proxy` — the data-plane entry for proxying requests into this sandbox.
- `urls.web` — the browser entry point, accessible once you enable a web link.

## Common Failures

- `template_not_found` — list templates again and retry with a name from that list.
- `sandbox_name_conflict` — pick another name or omit `--name` to let the platform generate one.
- `email_verification_required` — verify the account before sandbox creation is allowed.
- `compute_quota_exceeded` or `storage_quota_exceeded` — check [Usage & Limits](/docs/usage-limits.md).
- `validation_error` — fix the request shape or field values and retry.

> For automation: always request JSON and capture `id` from the create response. Use `id` for every subsequent operation, not `name`.

## Read Next

- [Browser Handoff](/docs/browser-handoff.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [Error Reference](/docs/error-reference.md)
