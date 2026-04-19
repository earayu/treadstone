# Sandbox Dual-Path: claim (default) vs direct (persist=true) provisioning
# Also covers invalid template rejection.
# Self-contained: registers its own user, no external dependencies.

# ── Setup: Register + Login + API Key ────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-05-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 201
[Captures]
user_id: jsonpath "$.id"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-05-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

# ── Verify email (admin fetches token) ─────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

GET {{base_url}}/v1/admin/verification-token-by-email?email=e2e-05-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-05-{{unique}}@test.treadstone.dev",
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
{"name": "e2e-dual-path-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── List Templates (get a valid name) ────────────────────────────────────────

GET {{base_url}}/v1/sandbox-templates
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1


# ── Unknown template name → 403 (metering runs before K8s template resolution) ─

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "nonexistent-template-xyz",
    "name": "e2e-bad-tmpl-{{unique}}"
}
HTTP 403
[Asserts]
jsonpath "$.error.code" == "template_not_allowed"


# ── Claim Path (persist=false, default) ──────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-claim-{{unique}}"
}
HTTP 202
[Captures]
claim_sandbox_id: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString
jsonpath "$.name" == "e2e-claim-{{unique}}"
jsonpath "$.status" == "creating"

GET {{base_url}}/v1/sandboxes/{{claim_sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.persist" == false
jsonpath "$.storage_size" == null


# Free tier: max_concurrent_running=1 — stopped sandboxes do not count; stop claim before second create (else HTTP 429).
GET {{base_url}}/v1/sandboxes/{{claim_sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
# CI / loaded clusters can keep a sandbox in "creating" longer than local runs;
# allow the same ~3 min readiness window used by the dedicated lifecycle tests.
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"

POST {{base_url}}/v1/sandboxes/{{claim_sandbox_id}}/stop
Authorization: Bearer {{api_key}}
HTTP 200

GET {{base_url}}/v1/sandboxes/{{claim_sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
# Stop is also async via the K8s control loop; give it up to ~60s in CI.
retry: 30
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "stopped"


# Free tier has 0 GiB storage quota — persist=true needs an admin storage grant (HTTP 402 otherwise).
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
    "reason": "E2E dual-path persist path"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-05-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200


# ── Direct Path (persist=true) ───────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-direct-{{unique}}",
    "persist": true,
    "storage_size": "5Gi"
}
HTTP 202
[Captures]
direct_sandbox_id: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString
jsonpath "$.name" == "e2e-direct-{{unique}}"
jsonpath "$.status" == "creating"

GET {{base_url}}/v1/sandboxes/{{direct_sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.persist" == true
jsonpath "$.storage_size" == "5Gi"


# ── List: both sandboxes visible ─────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.total" >= 2


# ── Cleanup ──────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{claim_sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/sandboxes/{{direct_sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
