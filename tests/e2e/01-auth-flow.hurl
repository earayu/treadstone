# Auth Flow: health → register → login → get user
# Self-contained: registers its own user, no external dependencies.

# ── Health Check ─────────────────────────────────────────────────────────────

GET {{base_url}}/health
HTTP 200
[Asserts]
jsonpath "$.status" == "ok"


# ── Register ─────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_01}}",
    "password": "{{test_password}}"
}
HTTP 201
[Captures]
user_id: jsonpath "$.id"
[Asserts]
jsonpath "$.email" == "{{email_01}}"
jsonpath "$.id" isString


# ── Login ────────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_01}}",
    "password": "{{test_password}}"
}
HTTP 200
[Asserts]
cookie "session" exists


# ── Get Current User ─────────────────────────────────────────────────────────

GET {{base_url}}/v1/auth/user
HTTP 200
[Asserts]
jsonpath "$.email" == "{{email_01}}"
jsonpath "$.is_active" == true
