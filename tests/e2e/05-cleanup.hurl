# Cleanup: login (with new_password since 04 changed it) → delete test user
# This runs last. The delete may return 400 if the user is the last admin
# or cannot delete self — both are acceptable, so we accept 204 or 400.

# ── Login ────────────────────────────────────────────────────────────────────

POST {{base_url}}/v1/auth/login
[FormParams]
username: {{test_email}}
password: {{new_password}}
HTTP *
[Asserts]
status < 300


# ── Delete Test User ────────────────────────────────────────────────────────
# Accept 204 (deleted) or 400 (self-delete / last admin protection).

DELETE {{base_url}}/v1/auth/users/{{user_id}}
HTTP *
[Asserts]
status < 500
