# Metering Admin API: tier templates, user plan management, compute/storage grants (single + batch)
# Uses pre-registered admin user (admin_email) from e2e-test.sh setup.

# ── Setup: Login as admin + API Key ──────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-metering-admin-key"}
HTTP 201
[Captures]
admin_api_key: jsonpath "$.key"
admin_api_key_id: jsonpath "$.id"


# ── GET /v1/admin/tier-templates — verify seeded tiers ──────────────────────

GET {{base_url}}/v1/admin/tier-templates
Authorization: Bearer {{admin_api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count >= 4


# ── PATCH /v1/admin/tier-templates/free — update grace_period ────────────────

PATCH {{base_url}}/v1/admin/tier-templates/free
Authorization: Bearer {{admin_api_key}}
Content-Type: application/json
{
    "grace_period_seconds": 900
}
HTTP 200
[Asserts]
jsonpath "$.tier" == "free"
jsonpath "$.grace_period_seconds" == 900
jsonpath "$.is_active" == true
jsonpath "$.users_affected" >= 0


# ── PATCH /v1/admin/tier-templates/free — restore original value ─────────────

PATCH {{base_url}}/v1/admin/tier-templates/free
Authorization: Bearer {{admin_api_key}}
Content-Type: application/json
{
    "grace_period_seconds": 600
}
HTTP 200
[Asserts]
jsonpath "$.grace_period_seconds" == 600


# ── Register target user for admin management tests ─────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_08}}",
    "password": "{{test_password}}"
}
HTTP 201
[Captures]
target_user_id: jsonpath "$.id"


# ── GET /v1/admin/users/{id}/usage — view target user's usage ────────────────

GET {{base_url}}/v1/admin/users/{{target_user_id}}/usage
Authorization: Bearer {{admin_api_key}}
HTTP 200
[Asserts]
jsonpath "$.tier" == "free"
jsonpath "$.compute.monthly_limit" == 10.0
jsonpath "$.compute.monthly_used" >= 0.0
jsonpath "$.compute.extra_remaining" == 50.0
jsonpath "$.compute.unit" == "credits"
jsonpath "$.storage.total_quota_gib" == 0
jsonpath "$.storage.unit" == "GiB"
jsonpath "$.limits.max_concurrent_running" == 1


# ── GET /v1/admin/users/{id}/usage — nonexistent user → 404 ─────────────────

GET {{base_url}}/v1/admin/users/nonexistent-user-xxx/usage
Authorization: Bearer {{admin_api_key}}
HTTP 404
[Asserts]
jsonpath "$.error.code" == "not_found"


# ── PATCH /v1/admin/users/{id}/plan — upgrade to pro tier ────────────────────

PATCH {{base_url}}/v1/admin/users/{{target_user_id}}/plan
Authorization: Bearer {{admin_api_key}}
Content-Type: application/json
{
    "tier": "pro"
}
HTTP 200
[Asserts]
jsonpath "$.tier" == "pro"
jsonpath "$.compute_credits_monthly_limit" == 100.0
jsonpath "$.storage_capacity_limit_gib" == 10
jsonpath "$.max_concurrent_running" == 3
jsonpath "$.max_sandbox_duration_seconds" == 7200


# ── Verify tier change via admin usage view ──────────────────────────────────

GET {{base_url}}/v1/admin/users/{{target_user_id}}/usage
Authorization: Bearer {{admin_api_key}}
HTTP 200
[Asserts]
jsonpath "$.tier" == "pro"
jsonpath "$.compute.monthly_limit" == 100.0
jsonpath "$.storage.total_quota_gib" == 10
jsonpath "$.limits.max_concurrent_running" == 3


# ── POST /v1/admin/users/{id}/compute-grants — issue compute credits ────────

POST {{base_url}}/v1/admin/users/{{target_user_id}}/compute-grants
Authorization: Bearer {{admin_api_key}}
Content-Type: application/json
{
    "amount": 100,
    "grant_type": "admin_grant",
    "reason": "E2E test grant"
}
HTTP 201
[Captures]
grant_id: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString
jsonpath "$.user_id" == "{{target_user_id}}"
jsonpath "$.original_amount" == 100.0
jsonpath "$.remaining_amount" == 100.0
jsonpath "$.grant_type" == "admin_grant"
jsonpath "$.reason" == "E2E test grant"
jsonpath "$.granted_at" isString


# ── Verify grant reflected in usage ──────────────────────────────────────────

GET {{base_url}}/v1/admin/users/{{target_user_id}}/usage
Authorization: Bearer {{admin_api_key}}
HTTP 200
[Asserts]
jsonpath "$.compute.extra_remaining" >= 100.0


# ── POST /v1/admin/compute-grants/batch — one valid + one invalid user ──────

POST {{base_url}}/v1/admin/compute-grants/batch
Authorization: Bearer {{admin_api_key}}
Content-Type: application/json
{
    "user_ids": ["{{target_user_id}}", "nonexistent-user-xxx"],
    "amount": 50,
    "grant_type": "campaign",
    "reason": "E2E batch test"
}
HTTP 200
[Asserts]
jsonpath "$.total_requested" == 2
jsonpath "$.succeeded" == 1
jsonpath "$.failed" == 1
jsonpath "$.results" count == 2


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{admin_api_key_id}}
HTTP 204
