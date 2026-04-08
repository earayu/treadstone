# Data plane: sandbox HTTP proxy (/v1/sandboxes/{id}/proxy/...)
# Requires agent-sandbox + runtime; polls until sandbox status is ready, then:
#   - proxy without Bearer → 401
#   - key with data_plane none → 403 on proxy
#   - POST /v1/shell/exec with default key → 200
# Self-contained user + verification (same pattern as 04-sandbox-crud).

# ── Setup: Register + verify + API key (full scope, default) ────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_09}}",
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

GET {{base_url}}/v1/admin/verification-token-by-email?email={{email_09}}
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_09}}",
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
{"name": "e2e-data-plane-full"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── Templates + create sandbox ───────────────────────────────────────────

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
    "name": "e2e-dp-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"


# ── Wait until ready (async provisioning) ───────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 30
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"
jsonpath "$.urls.proxy" contains "/proxy"


# ── Data plane: no Bearer (cookie session is not valid here) ──────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/browser/info
HTTP 401
[Asserts]
jsonpath "$.error.code" == "auth_invalid"


# ── Key with data_plane none cannot use proxy ───────────────────────────────

POST {{base_url}}/v1/auth/api-keys
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "name": "e2e-data-plane-cp-only",
    "scope": {
        "control_plane": true,
        "data_plane": { "mode": "none" }
    }
}
HTTP 201
[Captures]
cp_only_key: jsonpath "$.key"
cp_only_key_id: jsonpath "$.id"

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/shell/exec
Authorization: Bearer {{cp_only_key}}
Content-Type: application/json
{
    "command": "echo should-not-run",
    "exec_dir": "/tmp"
}
HTTP 403
[Asserts]
jsonpath "$.error.code" == "forbidden"

DELETE {{base_url}}/v1/auth/api-keys/{{cp_only_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204


# ── Data plane: shell exec with full-scope key ─────────────────────────────

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/shell/exec
Authorization: Bearer {{api_key}}
Content-Type: application/json
[Options]
retry: 8
retry-interval: 3s
{
    "command": "echo e2e-data-plane-ok && pwd",
    "exec_dir": "/tmp"
}
HTTP 200
[Asserts]
jsonpath "$.success" == true
jsonpath "$.data.status" == "completed"
jsonpath "$.data.output" contains "e2e-data-plane-ok"


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204
