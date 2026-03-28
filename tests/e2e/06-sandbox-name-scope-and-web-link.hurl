# Sandbox naming + web links:
# - same user cannot reuse a sandbox name
# - different users can use the same sandbox name
# - browser URLs are based on sandbox.id, not sandbox.name
# - deleting a sandbox revokes its web link immediately

# ── User A setup ─────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-06-a-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-06-a-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

GET {{base_url}}/v1/test-support/emails/latest-verification?email=e2e-06-a-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token_a: jsonpath "$.token"

POST {{base_url}}/v1/auth/verification/confirm
Content-Type: application/json
{
    "token": "{{verify_token_a}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-name-scope-a"}
HTTP 201
[Captures]
api_key_a: jsonpath "$.key"
api_key_id_a: jsonpath "$.id"


# ── Resolve a valid template ────────────────────────────────────────────────

GET {{base_url}}/v1/sandbox-templates
Authorization: Bearer {{api_key_a}}
HTTP 200
[Captures]
template_name: jsonpath "$.items[0].name"
[Asserts]
jsonpath "$.items" count >= 1


# ── User A creates a sandbox and gets an id-based web URL ───────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key_a}}
Content-Type: application/json
{
    "template": "{{template_name}}",
    "name": "shared-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id_a: jsonpath "$.id"
[Asserts]
jsonpath "$.name" == "shared-{{unique}}"
jsonpath "$.urls.web" startsWith "http://sandbox-{{sandbox_id_a}}.sandbox.localhost/_treadstone/open?token="

POST {{base_url}}/v1/sandboxes/{{sandbox_id_a}}/web-link
Authorization: Bearer {{api_key_a}}
HTTP 200
[Asserts]
jsonpath "$.web_url" startsWith "http://sandbox-{{sandbox_id_a}}.sandbox.localhost"
jsonpath "$.open_link" startsWith "http://sandbox-{{sandbox_id_a}}.sandbox.localhost/_treadstone/open?token="

GET {{base_url}}/v1/sandboxes/{{sandbox_id_a}}/web-link
Authorization: Bearer {{api_key_a}}
HTTP 200
[Asserts]
jsonpath "$.enabled" == true
jsonpath "$.web_url" startsWith "http://sandbox-{{sandbox_id_a}}.sandbox.localhost"


# ── Same user cannot reuse the same name ────────────────────────────────────

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key_a}}
Content-Type: application/json
{
    "template": "{{template_name}}",
    "name": "shared-{{unique}}"
}
HTTP 409
[Asserts]
jsonpath "$.error.code" == "sandbox_name_conflict"


# ── User B can reuse the same name ──────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "e2e-06-b-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "e2e-06-b-{{unique}}@test.treadstone.dev",
    "password": "{{test_password}}"
}
HTTP 200

GET {{base_url}}/v1/test-support/emails/latest-verification?email=e2e-06-b-{{unique}}@test.treadstone.dev
HTTP 200
[Captures]
verify_token_b: jsonpath "$.token"

POST {{base_url}}/v1/auth/verification/confirm
Content-Type: application/json
{
    "token": "{{verify_token_b}}"
}
HTTP 200

POST {{base_url}}/v1/auth/api-keys
Content-Type: application/json
{"name": "e2e-name-scope-b"}
HTTP 201
[Captures]
api_key_b: jsonpath "$.key"
api_key_id_b: jsonpath "$.id"

POST {{base_url}}/v1/sandboxes
Authorization: Bearer {{api_key_b}}
Content-Type: application/json
{
    "template": "{{template_name}}",
    "name": "shared-{{unique}}"
}
HTTP 202
[Captures]
sandbox_id_b: jsonpath "$.id"
[Asserts]
jsonpath "$.id" isString


# ── Deleting User A sandbox revokes the web link immediately ────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id_a}}
Authorization: Bearer {{api_key_a}}
HTTP 204

GET {{base_url}}/v1/sandboxes/{{sandbox_id_a}}/web-link
Authorization: Bearer {{api_key_a}}
HTTP 200
[Asserts]
jsonpath "$.enabled" == false


# ── Cleanup ─────────────────────────────────────────────────────────────────

DELETE {{base_url}}/v1/sandboxes/{{sandbox_id_b}}
Authorization: Bearer {{api_key_b}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id_a}}
Authorization: Bearer {{api_key_a}}
HTTP 204

DELETE {{base_url}}/v1/auth/api-keys/{{api_key_id_b}}
Authorization: Bearer {{api_key_b}}
HTTP 204
