# Admin Operations

## What this page is for

Give admins the shortest reliable map for metering and user-plan operations.

## Use this when

- You are an admin changing user plans or tier templates.
- You need to issue compute or storage grants.
- You need to inspect platform stats or batch-resolve emails.

## Shortest path

```text
GET   /v1/admin/stats
GET   /v1/admin/tier-templates
PATCH /v1/admin/tier-templates/{tier}
PATCH /v1/admin/users/{user_id}/plan
POST  /v1/admin/users/{user_id}/compute-grants
POST  /v1/admin/users/{user_id}/storage-grants
```

## Hard rules

- Admin routes require an admin account on the control plane.
- Tier-template changes and user-plan overrides are separate operations.
- Batch grant routes exist when one-off user-by-user mutation is too slow.

## Platform Stats

```text
GET /v1/admin/stats
```

This aggregates:

- user counts
- sandbox counts by status
- total current-period compute usage
- allocated and consumed storage

## Tier Templates

```text
GET   /v1/admin/tier-templates
PATCH /v1/admin/tier-templates/{tier_name}
```

Use tier-template updates when you want to change the baseline shape of a tier.

## User Plans

```text
GET   /v1/admin/users/{user_id}/usage
PATCH /v1/admin/users/{user_id}/plan
```

Use user-plan updates when you want to move a user between tiers or attach overrides.

## Grants

Per-user routes:

- `POST /v1/admin/users/{user_id}/compute-grants`
- `POST /v1/admin/users/{user_id}/storage-grants`

Batch routes:

- `POST /v1/admin/compute-grants/batch`
- `POST /v1/admin/storage-grants/batch`

## User Resolution

- `GET /v1/admin/users/lookup-by-email`
- `POST /v1/admin/users/resolve-emails`

Use these when you have email addresses but not user IDs.

## Waitlist and Verification Utilities

Admin routes also expose waitlist-management and verification helper paths. Use them when operating the public signup funnel or support flows.

## For Agents

- If a task says “upgrade user X”, resolve the user ID first.
- If a task says “change the default tier”, patch the tier template, not the individual user plan.
