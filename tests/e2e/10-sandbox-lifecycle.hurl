# Sandbox lifecycle: stop → stopped → start → ready → delete
# Self-contained user + verification.

# ── Setup ───────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_10}}",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

GET {{base_url}}/v1/admin/verification-token-by-email?email={{email_10}}
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_10}}",
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
{"name": "e2e-lifecycle-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"

GET {{base_url}}/v1/sandbox-templates
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{sandbox_template}}",
    "name": "e2e-lc-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"


# ── Wait ready ──────────────────────────────────────────────────────────────
# CI may keep status "creating" longer than ~60s; allow ~3 min (same as 09-data-plane-proxy).

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"


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


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
