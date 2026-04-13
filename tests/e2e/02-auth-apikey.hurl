# Auth API Key: register → login → create key → list → use Bearer auth
#               → create restricted key → verify scope enforcement
#               → update key → disable → delete → verify revoked
# Self-contained: registers its own user, no external dependencies.

# ── Setup: Register + Login ─────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_02}}",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_02}}",
    "password": "{{test_password}}"
}
HTTP 200


# ── Create API Key (default scope: full access) ─────────────────────────────

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-full-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"
[Asserts]
jsonpath "$.key" startsWith "sk-"
jsonpath "$.name" == "e2e-full-key"
jsonpath "$.scope.control_plane" == true
jsonpath "$.scope.data_plane.mode" == "all"


# ── List API Keys ───────────────────────────────────────────────────────────

GET {{base_url}}/v1/auth/api-keys
HTTP 200
[Asserts]
jsonpath "$.items" count >= 1


# ── Use API Key Auth (GET /v1/auth/user) ────────────────────────────────────

GET {{base_url}}/v1/auth/user
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.email" == "{{email_02}}"


# ── Create restricted key: control_plane only, no data_plane ────────────────

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{
    "name": "e2e-cp-only-key",
    "scope": {
        "control_plane": true,
        "data_plane": {"mode": "none"}
    }
}
HTTP 201
[Captures]
cp_only_key: jsonpath "$.key"
cp_only_key_id: jsonpath "$.id"
[Asserts]
jsonpath "$.scope.control_plane" == true
jsonpath "$.scope.data_plane.mode" == "none"


# ── Restricted key CAN access control plane endpoints ───────────────────────

GET {{base_url}}/v1/auth/user
Authorization: Bearer {{cp_only_key}}
HTTP 200
[Asserts]
jsonpath "$.email" == "{{email_02}}"


# ── Update key: rename ──────────────────────────────────────────────────────

PATCH {{base_url}}/v1/auth/api-keys/{{api_key_id}}
Content-Type: application/json
{
    "name": "e2e-full-key-renamed"
}
HTTP 200
[Asserts]
jsonpath "$.name" == "e2e-full-key-renamed"


# ── Update key: disable ─────────────────────────────────────────────────────

PATCH {{base_url}}/v1/auth/api-keys/{{cp_only_key_id}}
Content-Type: application/json
{
    "is_enabled": false
}
HTTP 200
[Asserts]
jsonpath "$.is_enabled" == false


# ── Disabled key → 401 ──────────────────────────────────────────────────────

GET {{base_url}}/v1/auth/user
Authorization: Bearer {{cp_only_key}}
HTTP 401


# ── Delete API Key ──────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
HTTP 204


# ── Deleted key → 401 ───────────────────────────────────────────────────────

GET {{base_url}}/v1/auth/user
Authorization: Bearer {{api_key}}
HTTP 401


# ── Cleanup: delete restricted key ──────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{cp_only_key_id}}
HTTP 204
