# API Key: register → login → create key → list keys → use key for auth → delete key
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


# ── Create API Key ───────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-test-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"
[Asserts]
jsonpath "$.key" startsWith "sk-"
jsonpath "$.name" == "e2e-test-key"


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


# ── Delete API Key ──────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
HTTP 204
