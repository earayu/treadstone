# Sandbox CRUD: register → login → create API key → list templates
#               → create sandbox → get detail → list → delete sandbox → delete key
# Self-contained: registers its own user, no external dependencies.

# ── Setup: Register + Login + API Key ────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_03}}",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_03}}",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-sandbox-key"}
HTTP 201
[Captures]
api_key: jsonpath "$.key"
api_key_id: jsonpath "$.id"


# ── List Sandbox Templates ──────────────────────────────────────────────────

GET {{base_url}}/v1/sandbox-templates
Authorization: Bearer {{api_key}}
HTTP 200
[Captures]
template_name: jsonpath "$.items[0].name"
[Asserts]
jsonpath "$.items" count >= 1


# ── Create Sandbox ──────────────────────────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
Content-Type: application/json
{
    "template": "{{template_name}}",
    "name": "e2e-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString
jsonpath "$.template" == "{{template_name}}"
jsonpath "$.status" isString


# ── Get Sandbox Detail ──────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.id" == "{{sandbox_id}}"
jsonpath "$.urls.proxy" isString


# ── List Sandboxes ──────────────────────────────────────────────────────────

GET {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key}}
HTTP 200
[Asserts]
jsonpath "$.total" >= 1
jsonpath "$.items" count >= 1


# ── Delete Sandbox ──────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id}}
Authorization: Bearer {{api_key}}
HTTP 204


# ── Cleanup: Delete API Key ─────────────────────────────────────────────────

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id}}
HTTP 204
