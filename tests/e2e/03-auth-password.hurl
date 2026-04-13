# Auth Password: register → login → change password → old password fails → new password works
#                → password reset request (always 200)
# Self-contained: registers its own user, no external dependencies.

# ── Setup: Register + Login ─────────────────────────────────────────────────

POST {{base_url}}/v1/auth/register
Content-Type: application/json
{
    "email": "{{email_04}}",
    "password": "{{test_password}}"
}
HTTP 201

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_04}}",
    "password": "{{test_password}}"
}
HTTP 200


# ── Change Password ─────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/change-password
Content-Type: application/json
{
    "old_password": "{{test_password}}",
    "new_password": "{{new_password}}"
}
HTTP 200
[Asserts]
jsonpath "$.detail" == "Password changed"


# ── Old password no longer works ─────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_04}}",
    "password": "{{test_password}}"
}
HTTP 400


# ── Login with new password ─────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
Content-Type: application/json
{
    "email": "{{email_04}}",
    "password": "{{new_password}}"
}
HTTP 200
[Asserts]
cookie "session" exists


# ── Verify session is active ────────────────────────────────────────────────

GET {{base_url}}/v1/auth/user
HTTP 200
[Asserts]
jsonpath "$.email" == "{{email_04}}"


# ── Password reset request (always returns 200 regardless of email) ─────────

POST {{base_url}}/v1/auth/password-reset/request
Content-Type: application/json
{
    "email": "{{email_04}}"
}
HTTP 200

POST {{base_url}}/v1/auth/password-reset/request
Content-Type: application/json
{
    "email": "nonexistent-e2e@test.treadstone.dev"
}
HTTP 200


# ── Password reset confirm with invalid token → 400 ─────────────────────────

POST {{base_url}}/v1/auth/password-reset/confirm
Content-Type: application/json
{
    "token": "invalid-token-xxx",
    "new_password": "SomeNew_Pass1!"
}
HTTP 400
[Asserts]
jsonpath "$.error.code" == "password_reset_token_invalid"
