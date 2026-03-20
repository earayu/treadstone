# Auth Flow: health → register → login → get user
# Cookies persist automatically across requests within this file.

# ── Health Check ─────────────────────────────────────────────────────────────

GET {{base_url}}/health
HTTP 200
[Asserts]
jsonpath "$.status" == "ok"


# ── Register ─────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{test_email}}",
    "password": "{{test_password}}"
}
HTTP 201
[Captures]
user_id: jsonpath "$.id"
[Asserts]
jsonpath "$.email" == "{{test_email}}"
jsonpath "$.id" isString


# ── Login ────────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
[FormParams]
username: {{test_email}}
password: {{test_password}}
HTTP *
[Asserts]
status < 300
cookie "session" exists


# ── Get Current User ─────────────────────────────────────────────────────────

GET {{base_url}}/v1/auth/user
HTTP 200
[Asserts]
jsonpath "$.email" == "{{test_email}}"
jsonpath "$.is_active" == true
