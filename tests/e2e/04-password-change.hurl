# Password Change: login → change password → login with new password
# Requires a registered user (run 01-auth-flow.hurl first via the wrapper).

# ── Login with Original Password ────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
[FormParams]
username: {{test_email}}
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
username: {{test_email}}
password: {{new_password}}
HTTP *
[Asserts]
status < 300
cookie "session" exists
