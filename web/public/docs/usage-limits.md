# Usage & Limits

Before creating a sandbox, the key question is: do I have budget? Before debugging a quota rejection, the key question is: which limit did I hit? This page answers both.

## Where To Look

- **Console**: [/app/usage](/app/usage) — visual breakdown of your current billing period
- `GET /v1/usage` — summary: compute remaining, storage available, concurrency state, and plan limits
- `GET /v1/usage/plan` — the full plan record, including the templates your plan allows
- `GET /v1/usage/sessions` — paginated history of past compute sessions
- `GET /v1/usage/storage-ledger` — paginated storage usage history
- `GET /v1/usage/grants` — active compute and storage grants applied to the account

The hosted CLI does not have a dedicated `usage` command today. Use the API directly or check the Console.

## Fields That Drive Decisions

From `GET /v1/usage`:

- `compute.total_remaining` — total compute seconds left in the current billing period
- `compute.monthly_remaining` — this calendar month's remaining compute
- `storage.available_gib` — storage quota remaining across all persistent sandboxes
- `limits.allowed_templates` — the template names the current plan permits
- `limits.max_concurrent_running` — how many sandboxes can run simultaneously
- `limits.current_running` — how many are running right now
- `limits.max_sandbox_duration_seconds` — the longest single run the plan allows
- `grace_period.active` — whether the account is currently in a grace period

## Quick Check

```bash
curl -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  https://api.treadstone-ai.dev/v1/usage
```

Read `compute.total_remaining` and `limits.current_running` before deciding whether to create or start another sandbox.

## When Quota Blocks You

- `compute_quota_exceeded` — wait for the next billing period or upgrade the plan.
- `concurrent_limit_exceeded` — stop another sandbox before creating or starting one more.
- `storage_quota_exceeded` — delete unused persistent sandboxes or increase quota.
- `sandbox_duration_exceeded` — lower `auto_stop_interval` or move to a plan with a longer max runtime.

> For automation: read `/v1/usage` before retrying quota failures. Do not blind-retry `compute_quota_exceeded` or `storage_quota_exceeded`.

## Read Next

- [Error Reference](/docs/error-reference.md)
- [API Reference](/docs/api-reference.md)
