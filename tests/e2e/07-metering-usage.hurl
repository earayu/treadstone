# Metering Usage API: register → login → api-key → usage summary, plan, sessions, grants
# Also verifies non-admin user is denied access to admin endpoints.
# Self-contained: registers its own user, no external dependencies.

# ── Setup: Register + Login + API Key ────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_07}}",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_07}}",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-metering-usage-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── GET /v1/usage — aggregate usage overview ────────────────────────────────

GET {{base_url}}/v1/usage
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.tier" == "free"
jsonpath "$.billing_period.start" isString
jsonpath "$.billing_period.end" isString
jsonpath "$.compute.compute_unit_hours" >= 0.0
jsonpath "$.compute.monthly_limit" == 10.0
jsonpath "$.compute.monthly_used" >= 0.0
jsonpath "$.compute.monthly_remaining" >= 0.0
jsonpath "$.compute.extra_remaining" == 50.0
jsonpath "$.compute.total_remaining" >= 0.0
jsonpath "$.compute.unit" == "CU-hours"
jsonpath "$.storage.current_used_gib" == 0
jsonpath "$.storage.total_quota_gib" == 0
jsonpath "$.storage.available_gib" == 0
jsonpath "$.storage.unit" == "GiB"
jsonpath "$.limits.max_concurrent_running" == 1
jsonpath "$.limits.max_sandbox_duration_seconds" == 1800
jsonpath "$.limits.current_running" == 0
jsonpath "$.grace_period.active" == false
jsonpath "$.grace_period.grace_period_seconds" == 600


# ── GET /v1/usage/plan — full UserPlan details ──────────────────────────────

GET {{base_url}}/v1/usage/plan
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.id" isString
jsonpath "$.user_id" isString
jsonpath "$.tier" == "free"
jsonpath "$.compute_units_monthly_limit" == 10.0
jsonpath "$.compute_units_monthly_used" >= 0.0
jsonpath "$.storage_capacity_limit_gib" == 0
jsonpath "$.max_concurrent_running" == 1
jsonpath "$.max_sandbox_duration_seconds" == 1800
jsonpath "$.allowed_templates" count >= 1
jsonpath "$.grace_period_seconds" == 600
jsonpath "$.billing_period_start" isString
jsonpath "$.billing_period_end" isString
jsonpath "$.grace_period_started_at" == null
jsonpath "$.created_at" isString
jsonpath "$.updated_at" isString


# ── GET /v1/usage/sessions — empty list (no sandbox running) ────────────────

GET {{base_url}}/v1/usage/sessions
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count == 0
jsonpath "$.total" == 0
jsonpath "$.limit" == 20
jsonpath "$.offset" == 0


# ── GET /v1/usage/sessions with filters ─────────────────────────────────────

GET {{base_url}}/v1/usage/sessions?status=active&limit=5&offset=0
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count == 0
jsonpath "$.limit" == 5
jsonpath "$.offset" == 0


# ── GET /v1/usage/grants — no welcome bonus when amount is 0 ─────────────────

GET {{base_url}}/v1/usage/grants
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.compute_grants" count == 0


# ── Non-admin access to admin endpoint → 403 ────────────────────────────────

GET {{base_url}}/v1/admin/tier-templates
Authorization: Bearer {{api_key}}
HTTP 403
[Asserts]
jsonpath "$.error.code" == "forbidden"


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
HTTP 204
