# Error Reference

## What this page is for

Translate common error codes into the next action.

## Use this when

- A request failed and you need to recover.
- You need the exact error envelope.
- You need to separate auth, quota, lifecycle, and storage failures.

## Shortest path

Read `error.code`, then map it below.

## Hard rules

- Do not parse only the message string.
- The error envelope is stable even when the message changes.
- Retry only after you know whether the error is transient or structural.

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

No credential was accepted.

Next action:

- add a saved session or API key for control-plane routes
- add an API key for data-plane routes

### `auth_invalid`

The credential is invalid, expired, or the wrong type for the route.

Next action:

- verify the key value
- verify whether the route is control plane or data plane

### `forbidden`

The caller is authenticated but not allowed.

Next action:

- check admin role
- check API-key scope
- check selected sandbox grants

### `template_not_found`

The requested template does not exist on the server.

Next action:

- list templates again and retry with a valid name

### `sandbox_name_conflict`

The current user already owns a sandbox with that name.

Next action:

- choose another name or omit the name and let the platform generate one

### `sandbox_not_found`

The sandbox does not exist for the current user.

Next action:

- re-check `sandbox_id`
- confirm ownership and deletion state

### `sandbox_not_ready`

The sandbox exists but is not ready for the requested operation.

Next action:

- inspect current status and wait or recover accordingly

### `storage_backend_not_ready`

Persistent storage is not available in the cluster.

Next action:

- fix the configured `StorageClass`
- retry only after cluster storage is ready

### `email_verification_required`

The account must be verified before sandbox creation.

Next action:

- complete verification or request a new verification link

### `compute_quota_exceeded`

Compute credits are exhausted.

Next action:

- inspect `/v1/usage`
- wait for the next period or issue a grant

### `storage_quota_exceeded`

Persistent storage quota is exhausted.

Next action:

- delete unused persistent sandboxes or increase quota

### `concurrent_limit_exceeded`

The user already has too many running sandboxes.

Next action:

- stop one sandbox before creating another

### `sandbox_duration_exceeded`

The requested auto-stop duration exceeds the current plan.

Next action:

- reduce `auto_stop_interval` or change the plan

### `validation_error`

The payload shape or parameter values are invalid.

Next action:

- fix the request and retry

## For Agents

- Build retry logic around `error.code`, not around free-form text.
- For quota or plan failures, read usage endpoints before deciding the next step.
