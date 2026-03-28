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

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-05-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

# ── Verify email ───────────────────────────────────────────────────────────

GET {{base_url}}/v1/test-support/emails/latest-verification?email=e2e-05-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

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
[Captures]
template_name: jsonpath "$.items[0].name"
[Asserts]
jsonpath "$.items" count >= 1


# ── Invalid Template → 404 ───────────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "nonexistent-template-xyz",
    "name": "e2e-bad-tmpl-{{unique}}"
}
HTTP 404
[Asserts]
jsonpath "$.error.code" == "template_not_found"


# ── Claim Path (persist=false, default) ──────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{template_name}}",
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


# ── Direct Path (persist=true) ───────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{template_name}}",
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
HTTP 204
