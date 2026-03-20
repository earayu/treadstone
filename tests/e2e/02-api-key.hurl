# API Key: login → create key → list keys → use key for auth → delete key
# Requires a registered user (run 01-auth-flow.hurl first via the wrapper).

# ── Login ────────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
[FormParams]
username: {{test_email}}
password: {{test_password}}
HTTP *
[Asserts]
status < 300


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


# ── Use API Key Auth (GET /v1/me) ───────────────────────────────────────────

GET {{base_url}}/v1/me
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.email" == "{{test_email}}"


# ── Delete API Key ──────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
HTTP 204
