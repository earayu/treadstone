# Auth Session: register → verify email → login → get user → logout → re-login → duplicate register 409
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
jsonpath "$.is_active" == true


# ── Verify email (admin fetches token) ───────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{admin_email}}",
    "password": "{{admin_password}}"
}
HTTP 200

GET {{base_url}}/v1/admin/verification-token-by-email?email={{email_01}}
HTTP 200
[Captures]
verify_token: jsonpath "$.token"

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_01}}",
    "password": "{{test_password}}"
}
HTTP 200

POST {{base_url}}/v1/auth/verification/confirm
Content-Type: application/json
{
    "token": "{{verify_token}}"
}
HTTP 200


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
jsonpath "$.id" == "{{user_id}}"
jsonpath "$.email" == "{{email_01}}"
jsonpath "$.is_active" == true
jsonpath "$.email_verified" == true
jsonpath "$.role" isString


# ── Logout ───────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/logout
HTTP 200
[Asserts]
jsonpath "$.detail" == "Logout successful"


# ── After logout, /v1/auth/user is unauthenticated ──────────────────────────

GET {{base_url}}/v1/auth/user
HTTP 401


# ── Re-login with same credentials ──────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_01}}",
    "password": "{{test_password}}"
}
HTTP 200
[Asserts]
cookie "session" exists

GET {{base_url}}/v1/auth/user
HTTP 200
[Asserts]
jsonpath "$.email" == "{{email_01}}"


# ── Duplicate register → 409 ────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_01}}",
    "password": "{{test_password}}"
}
HTTP 409
[Asserts]
jsonpath "$.error.code" == "user_already_exists"
