# Sandbox Quota Enforcement: free tier limits → admin grants → success
# Tests: concurrent sandbox limit (max 1 for free), storage quota enforcement,
#         admin compute/storage grants unlock further creation.
# Self-contained: registers its own user + email verification.

# ── Setup: Register + Verify + API Key ──────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-08-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 201
[Captures]
user_id: jsonpath "$.id"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

GET {{base_url}}/v1/admin/verification-token-by-email?email=e2e-08-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-08-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/verification/confirm
Content-Type: application/json
{
    "token": "{{verify_token}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-quota-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── Verify free tier limits ─────────────────────────────────────────────────

GET {{base_url}}/v1/usage
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.tier" == "free"
jsonpath "$.limits.max_concurrent_running" == 1
jsonpath "$.storage.total_quota_gib" == 0


# ── Create first sandbox (should succeed) ───────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-quota-1-{{unique}}"
}
HTTP 202
[Captures]
sandbox_1_id: jsonpath "$.id"

# Wait until first sandbox is ready (counts as running)
GET {{base_url}}/v1/sandboxes/{{sandbox_1_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"


# ── Second sandbox while first is running → 429 (quota exceeded) ────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-quota-2-{{unique}}"
}
HTTP 429
[Asserts]
jsonpath "$.error.code" == "sandbox_quota_exceeded"


# ── Persistent sandbox without storage quota → 402 ──────────────────────────
# Stop first sandbox so concurrency check passes, then test storage quota.

POST {{base_url}}/v1/sandboxes/{{sandbox_1_id}}/stop
Authorization: Bearer {{api_key}}
HTTP 200

GET {{base_url}}/v1/sandboxes/{{sandbox_1_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 20
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "stopped"

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-quota-persist-{{unique}}",
    "persist": true,
    "storage_size": "5Gi"
}
HTTP 402
[Asserts]
jsonpath "$.error.code" == "storage_quota_exceeded"


# ── Admin grants storage quota ──────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

POST {{base_url}}/v1/admin/users/{{user_id}}/storage-grants
Content-Type: application/json
{
    "size_gib": 10,
    "grant_type": "admin_grant",
    "reason": "E2E quota enforcement test"
}
HTTP 201

# Switch back to test user
POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-08-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200


# ── Now persistent sandbox creation succeeds ────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-quota-persist-{{unique}}",
    "persist": true,
    "storage_size": "5Gi"
}
HTTP 202
[Captures]
sandbox_persist_id: jsonpath "$.id"
[Asserts]
jsonpath "$.persist" == true


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_1_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/sandboxes/{{sandbox_persist_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
