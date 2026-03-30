# Create a Sandbox

Use this page when you already know you need a sandbox and want the fields and controls that actually matter.

## Do This

```bash
treadstone --json templates list
treadstone --json sandboxes create \
  --template aio-sandbox-tiny \
  --name demo \
  --label project:docs \
  --auto-stop-interval 60 \
  --auto-delete-interval -1
```

If you need persistent storage, add `--persist --storage-size 5Gi`.

## Set These Fields On Purpose

- `template`: must come from `templates list` or `/v1/sandbox-templates`.
- `name`: optional human label; unique only within your own account.
- `label`: repeatable `key:value` metadata for list filtering.
- `auto-stop-interval`: inactivity timeout in minutes. `0` means never auto-stop.
- `auto-delete-interval`: minutes after stop before deletion. `-1` disables auto-delete.
- `persist` and `storage_size`: attach persistent storage only when you actually need it.

## Save These Fields

- `id`
- `status`
- `urls.proxy`
- `urls.web`

`id` is the machine identifier. Every follow-up action uses it.

## Rules That Matter

- Sandbox names are for humans. Follow-up commands use `sandbox_id`.
- `storage_size` is only valid when `persist=true`.
- Allowed templates and storage sizes depend on your plan and the server configuration.
- `urls.web` is only useful as a browser entry point when sandbox web links are enabled.

## Common Failures

- `template_not_found`: list templates again and retry with a valid name.
- `sandbox_name_conflict`: pick another name or omit `--name`.
- `email_verification_required`: verify the account before creating sandboxes.
- `validation_error`: fix the request shape or field values and retry.

> For automation: always request JSON and capture `id` from the create response. Do not scrape table output.

## Read Next

- [Browser Handoff](/docs/browser-handoff.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [Error Reference](/docs/error-reference.md)
