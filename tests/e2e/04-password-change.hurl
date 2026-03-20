# Password Change: register → login → change password → login with new password
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
[FormParams]
username: {{email_04}}
password: {{test_password}}
HTTP *
[Asserts]
status < 300


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


# ── Login with New Password ─────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
[FormParams]
username: {{email_04}}
password: {{new_password}}
HTTP *
[Asserts]
status < 300
cookie "session" exists
