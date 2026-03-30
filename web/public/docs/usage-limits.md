# Usage & Limits

Use this page when you need to answer two questions fast: can I run another sandbox, and why did the platform reject my request?

## Look Here First

- Console: [/app/usage](/app/usage)
- API summary: `GET /v1/usage`
- API detail: `GET /v1/usage/plan`, `GET /v1/usage/sessions`, `GET /v1/usage/grants`

The hosted product does not expose a dedicated CLI `usage` command today.

## Fields That Actually Change Your Next Move

- `compute.total_remaining`
- `compute.monthly_remaining`
- `storage.available_gib`
- `limits.allowed_templates`
- `limits.max_concurrent_running`
- `limits.current_running`
- `limits.max_sandbox_duration_seconds`
- `grace_period.active`

## Example

```bash
curl -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  https://api.treadstone-ai.dev/v1/usage
```

Use the summary response to decide whether to create another sandbox, switch templates, shorten runtime, or clean up storage.

## When Limits Block You

- `compute_quota_exceeded`: wait for the next billing period or change the plan.
- `concurrent_limit_exceeded`: stop another sandbox first.
- `storage_quota_exceeded`: delete unused persistent sandboxes or increase quota.
- `sandbox_duration_exceeded`: lower `auto_stop_interval` or move to a plan that allows longer runs.

## Useful Detail Endpoints

- `/v1/usage/plan`: the full plan record and allowed templates
- `/v1/usage/sessions`: paginated compute sessions
- `/v1/usage/storage-ledger`: paginated storage usage history
- `/v1/usage/grants`: active compute and storage grants

> For automation: read `/v1/usage` before retrying quota failures. Do not blind-retry `compute_quota_exceeded` or `storage_quota_exceeded`.

## Read Next

- [Error Reference](/docs/error-reference.md)
- [API Reference](/docs/api-reference.md)
