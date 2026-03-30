# Usage and Quotas

## What this page is for

Show how a regular user reads limits, usage, grants, and current billing-period state.

## Use this when

- You need to know why sandbox creation is being blocked.
- You want to read compute usage or persistent storage usage.
- You want to inspect grants and plan limits from the user side.

## Shortest path

```bash
curl -s "$BASE_URL/v1/usage" -H "Authorization: Bearer $TREADSTONE_API_KEY"
curl -s "$BASE_URL/v1/usage/plan" -H "Authorization: Bearer $TREADSTONE_API_KEY"
curl -s "$BASE_URL/v1/usage/sessions?limit=20&offset=0" -H "Authorization: Bearer $TREADSTONE_API_KEY"
curl -s "$BASE_URL/v1/usage/grants" -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

## Hard rules

- The plan is the base limit. Grants extend it.
- Usage pages are read-only from the user side.
- Session history and storage ledger history are paginated with `limit` and `offset`.

## Routes

- `GET /v1/usage`
- `GET /v1/usage/plan`
- `GET /v1/usage/sessions`
- `GET /v1/usage/storage-ledger`
- `GET /v1/usage/grants`

## Read the Summary First

`GET /v1/usage` gives the compact view:

- tier
- billing period
- compute used, remaining, and total remaining
- storage used and available
- current running versus max concurrent
- grace-period state

## Read the Full Plan

`GET /v1/usage/plan` gives the raw plan object:

- `compute_units_monthly_limit`
- `storage_capacity_limit_gib`
- `max_concurrent_running`
- `max_sandbox_duration_seconds`
- `allowed_templates`
- `grace_period_seconds`
- `overrides`

## Inspect Compute Sessions

```text
GET /v1/usage/sessions?status=active|completed|all&limit=20&offset=0
```

Use this when you need to see what actually consumed compute.

## Inspect the Storage Ledger

```text
GET /v1/usage/storage-ledger?status=active|released|all&limit=20&offset=0
```

Use this when persistent sandboxes are consuming storage quota.

## Inspect Grants

`GET /v1/usage/grants` returns:

- compute grants
- storage quota grants

## For Agents

- If create fails with quota-related errors, read `/v1/usage` before retrying.
- If you need to explain why a user is blocked, use `/v1/usage/plan` plus `/v1/usage/grants`.
