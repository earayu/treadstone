# Error Reference

Every error response from the Treadstone API has the same shape. Build retry and recovery logic around `error.code` — it is stable. Do not parse `message`; it is human-readable prose and may change.

This page lists **common** public codes integrators see most often. Additional codes exist (for example `template_not_allowed`, `sandbox_unreachable`, `sandbox_timeout`, `invalid_transition`, `email_verification_token_invalid`, `email_already_verified`, `conflict`, `bad_request`, `not_found`). The authoritative set is implemented in `treadstone/core/errors.py` in the repository; cross-check there when handling a new code.

## Error Envelope

```json
{
  "error": {
    "code": "snake_case_code",
    "message": "Human-readable detail.",
    "status": 409
  }
}
```

## Common Error Codes

### `auth_required`

No accepted credential was provided.

Next step: sign in, add a saved session, or send an API key.

### `auth_invalid`

The credential is invalid, expired, disabled, or the wrong type for that route.

Next step: verify the key or switch to the right auth mode for the surface you are calling.

### `forbidden`

The caller is authenticated but not allowed.

Next step: check API key scope, selected sandbox grants, and whether the route is admin-only.

### `email_verification_required`

The account must be verified before sandbox creation.

Next step: verify the account or request another verification email.

### `template_not_found`

The template name does not exist on the server.

Next step: list templates again and retry with a valid name.

### `template_not_allowed`

The template exists but is not allowed on the current plan tier.

Next step: pick a template from `limits.allowed_templates` in usage responses, or upgrade the plan.

### `sandbox_name_conflict`

Your account already owns a sandbox with that name.

Next step: choose another name or let Treadstone generate one.

### `sandbox_not_found`

The sandbox does not exist for the current account.

Next step: re-check `sandbox_id`, ownership, and deletion state.

### `sandbox_not_ready`

The sandbox exists but is not ready for that action yet.

Next step: inspect current status, wait, or recover the lifecycle state first.

### `sandbox_unreachable`

The platform could not reach the sandbox workload (upstream connectivity failure).

Next step: retry; if it persists, inspect sandbox status and platform health.

### `sandbox_timeout`

The sandbox did not respond within the platform timeout.

Next step: retry; reduce load or inspect the workload inside the sandbox.

### `invalid_transition`

The requested lifecycle change is not valid from the sandbox’s current state.

Next step: read current `status` and use an allowed transition (see [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)).

### `compute_quota_exceeded`

No compute budget is available for another run.

Next step: open [Usage & Limits](/docs/usage-limits.md), wait for the next billing period, or change the plan.

### `storage_quota_exceeded`

No persistent storage quota is available for the requested allocation.

Next step: delete unused persistent sandboxes or increase quota.

### `concurrent_limit_exceeded`

The account already has too many running sandboxes.

Next step: stop another sandbox before creating or starting one more.

### `sandbox_duration_exceeded`

The requested auto-stop duration is longer than the current plan allows.

Next step: lower `auto_stop_interval` or move to a plan that allows longer runtimes.

### `storage_backend_not_ready`

Persistent storage is temporarily unavailable on the platform.

Next step: retry later. If the error persists, contact support.

### `validation_error`

The payload shape or parameter values are invalid.

Next step: fix the request and retry.

> For automation: do not blind-retry quota or validation failures. Read usage or fix the request first.
