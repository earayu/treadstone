# Troubleshooting

## What this page is for

Provide the shortest recovery map for the failures people will hit first.

## Use this when

- The CLI or API flow stopped working.
- The proxy or browser hand-off path is broken.
- Persistent sandboxes or quota checks are failing.

## Shortest path

1. Read the error code.
2. Check whether the failure is control plane, data plane, or cluster configuration.
3. Retry only after the underlying condition changes.

## Hard rules

- Do not treat every failure as a transient retry.
- Separate auth failures from runtime failures.
- Separate platform misconfiguration from user-level request mistakes.

## Auth Failures

### Symptom

- `auth_required`
- `auth_invalid`
- `forbidden`

### Checks

- does the request need a session or an API key
- is the route control plane or data plane
- does the API key have the required scope

## Sandbox Creation Failures

### Symptom

- `template_not_found`
- `sandbox_name_conflict`
- `email_verification_required`
- `storage_backend_not_ready`

### Checks

- list templates again
- choose a new name
- verify the account
- verify the configured storage class

## Proxy Failures

### Symptom

- `sandbox_not_ready`
- `sandbox_unreachable`

### Checks

- inspect current sandbox status from the control plane
- confirm the sandbox is owned by the caller
- confirm the proxy credential is an API key

## Browser-Handoff Failures

### Symptom

- `urls.web` missing
- web-link creation fails
- returned browser URL points at the wrong host

### Checks

- `TREADSTONE_SANDBOX_DOMAIN`
- `TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX`
- `TREADSTONE_APP_BASE_URL`

## Quota Failures

### Symptom

- `compute_quota_exceeded`
- `storage_quota_exceeded`
- `concurrent_limit_exceeded`
- `sandbox_duration_exceeded`

### Checks

- `/v1/usage`
- `/v1/usage/plan`
- `/v1/usage/grants`

## For Agents

- If you cannot classify the failure, read the exact `error.code` aloud to yourself and route from there.
- If the proxy path fails, inspect control-plane state before trying different proxy paths.
