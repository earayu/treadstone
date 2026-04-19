# Data Plane Proxy: auth + scope enforcement on sandbox proxy endpoints
# Tests: no Bearer → 401, data_plane=none key → 403, full-scope key → 200,
#         control_plane=false key can still use data plane.
# Self-contained: registers its own user + email verification.

# ── Setup: Register + Verify + API Key (full scope, default) ────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-15-{{unique}}@test.treadstone.dev",
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

GET {{base_url}}/v1/admin/verification-token-by-email?email=e2e-15-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-15-{{unique}}@test.treadstone.dev",
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


# ── Templates + create sandbox ──────────────────────────────────────────────

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
    "name": "e2e-dp2-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"


# ── Wait until ready ────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
[Options]
retry: 90
retry-interval: 2s
HTTP 200
[Asserts]
jsonpath "$.status" == "ready"
jsonpath "$.urls.proxy" contains "/proxy"


# ── No Bearer (cookie session is not valid for proxy) → 401 ─────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/browser/info
HTTP 401
[Asserts]
jsonpath "$.error.code" == "auth_invalid"


# ── Key with data_plane=none cannot use proxy → 403 ─────────────────────────

POST {{base_url}}/v1/auth/api-keys
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "name": "e2e-dp-cp-only",
    "scope": {
        "control_plane": true,
        "data_plane": {"mode": "none"}
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


# ── Key with control_plane=false, data_plane=all CAN use proxy ───────────────

POST {{base_url}}/v1/auth/api-keys
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "name": "e2e-dp-only",
    "scope": {
        "control_plane": false,
        "data_plane": {"mode": "all"}
    }
}
HTTP 201
[Captures]
dp_only_key: jsonpath "$.key"
dp_only_key_id: jsonpath "$.id"

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/shell/exec
Authorization: Bearer {{dp_only_key}}
Content-Type: application/json
[Options]
# A sandbox can report status=ready slightly before the proxied workload is
# consistently reachable; keep a second retry window for proxy-path readiness.
retry: 12
retry-interval: 3s
{
    "command": "echo e2e-dp-only-ok",
    "exec_dir": "/tmp"
}
HTTP 200
[Asserts]
jsonpath "$.success" == true
jsonpath "$.data.output" contains "e2e-dp-only-ok"

# data_plane-only key cannot access control plane
GET {{base_url}}/v1/auth/user
Authorization: Bearer {{dp_only_key}}
HTTP 403

DELETE {{base_url}}/v1/auth/api-keys/{{dp_only_key_id}}
Authorization: Bearer {{api_key}}
HTTP 204


# ── Full-scope key: shell exec ──────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes/{{sandbox_id}}/proxy/v1/shell/exec
Authorization: Bearer {{api_key}}
Content-Type: application/json
[Options]
retry: 12
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
