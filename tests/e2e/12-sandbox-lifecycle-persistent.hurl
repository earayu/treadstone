# Sandbox Lifecycle (Persistent): admin storage grant → create persistent → READY
#   → snapshot → wait snapshot complete → stop → start → delete
#   → verify storage-ledger records released
# Self-contained: registers its own user + email verification.

# ── Setup: Register + Verify + API Key ──────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-06-{{unique}}@test.treadstone.dev",
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

GET {{base_url}}/v1/admin/verification-token-by-email?email=e2e-06-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-06-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/verification/confirm
Content-Type: application/json
{
    "token": "{{verify_token}}"
}
HTTP 200


# ── Admin: grant storage quota (free tier has 0 GiB) ────────────────────────

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
    "reason": "E2E persistent sandbox test"
}
HTTP 201
[Asserts]
jsonpath "$.id" isString
jsonpath "$.size_gib" == 10


# ── Switch back to test user ────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-06-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-persist-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── Verify storage quota available ──────────────────────────────────────────

GET {{base_url}}/v1/usage
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.storage.total_quota_gib" >= 10
jsonpath "$.storage.available_gib" >= 5


# ── Create persistent sandbox ───────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-persist-{{unique}}",
    "persist": true,
    "storage_size": "5Gi"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"
[Asserts]
jsonpath "$.name" == "e2e-persist-{{unique}}"
jsonpath "$.persist" == true
jsonpath "$.storage_size" == "5Gi"
jsonpath "$.status" == "creating"


# ── Wait until ready ────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"


# ── Verify storage ledger has active entry ──────────────────────────────────

GET {{base_url}}/v1/usage/storage-ledger?status=active
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1


# ── Snapshot ────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/snapshot
Authorization: Bearer {{api_key}}
HTTP 202
[Asserts]
jsonpath "$.id" == "{{sandbox_id}}"

# Wait for snapshot to complete (pending_operation clears)
GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 60
retry-interval: 3s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"
jsonpath "$.pending_operation" == null


# ── Stop → Stopped ──────────────────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/stop
Authorization: Bearer {{api_key}}
HTTP 200

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 20
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "stopped"


# ── Start → Ready (data persists) ───────────────────────────────────────────

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/start
Authorization: Bearer {{api_key}}
HTTP 200

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"
jsonpath "$.persist" == true


# ── Delete ──────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204


# ── Verify storage ledger released (may take a moment for sync) ─────────────

GET {{base_url}}/v1/usage/storage-ledger?status=released
Authorization: Bearer {{api_key}}
[Options]
retry: 10
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
