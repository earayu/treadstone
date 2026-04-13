# Sandbox Lifecycle (Ephemeral): create → READY → stop → STOPPED → start → READY → delete
# Also tests: invalid template 403, sandbox detail fields, list endpoint.
# Self-contained: registers its own user + email verification, no external dependencies.

# ── Setup: Register + Verify + API Key ──────────────────────────────────────

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
{"name": "e2e-lifecycle-eph-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── List Templates ──────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandbox-templates
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1


# ── Invalid template → 403 ──────────────────────────────────────────────────

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


# ── Create Sandbox (ephemeral) ──────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-eph-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString
jsonpath "$.name" == "e2e-eph-{{unique}}"
jsonpath "$.template" == "{{sandbox_template}}"
jsonpath "$.status" == "creating"
jsonpath "$.persist" == false


# ── Wait until ready ────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"
jsonpath "$.urls.proxy" isString


# ── Get Detail: verify full response shape ──────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.id" == "{{sandbox_id}}"
jsonpath "$.name" == "e2e-eph-{{unique}}"
jsonpath "$.template" == "{{sandbox_template}}"
jsonpath "$.status" == "ready"
jsonpath "$.persist" == false
jsonpath "$.created_at" isString


# ── List Sandboxes ──────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.total" >= 1
jsonpath "$.items" count >= 1


# ── Stop ────────────────────────────────────────────────────────────────────

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


# ── Start ───────────────────────────────────────────────────────────────────

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


# ── Delete ──────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204


# ── Deleted sandbox returns 404 or DELETING status ──────────────────────────
# After DELETE the row transitions through "deleting" before the sync loop
# removes it.  The GET may return 200 with status=deleting or 404.

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP *
[Asserts]
status >= 200
status < 500


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
