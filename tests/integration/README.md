# Integration Tests

Integration tests run against a real Neon PostgreSQL database to verify end-to-end database interactions.

## Prerequisites

1. Create a **test branch** in your Neon project (do not use the main branch)
2. Copy `.env.test.example` to `.env.test` and fill in the test branch connection string:

```bash
cp tests/integration/.env.test.example tests/integration/.env.test
# Edit .env.test with your Neon test branch connection string
```

3. Ensure Alembic migrations have been applied on the test branch:

```bash
make migrate
```

> **Note:** `.env.test` contains database credentials and is excluded by `.gitignore`. It will never be committed.

## Running

```bash
make test-all          # Run all tests (including integration)
```

Or run integration tests only:

```bash
uv run pytest tests/integration/ -v -m integration
```

## How It Works

- `conftest.py` reads `TREADSTONE_DATABASE_URL` from `.env.test` before each test function
- It rebuilds the SQLAlchemy async engine with that URL, replacing the global engine
- If `.env.test` does not exist, falls back to the default connection string in the root `.env`
- Each test automatically cleans up any data it created (using unique token prefixes)

## Test Inventory

| Test | What it verifies |
|------|-----------------|
| `test_tables_exist` | Alembic migration correctly created user/oauth_account/api_key tables and removed invitation |
| `test_register_creates_user_in_db` | Register API creates a user record in the real DB |
| `test_full_auth_flow` | Full flow: register → login → get user → change password → login with new password |
| `test_duplicate_register_returns_409` | Duplicate email registration returns 409 Conflict |
| `test_config_endpoint_returns_auth_info` | `/api/config` returns correct auth configuration |
| `test_neon_connection_and_version` | Basic connectivity check (in `test_db.py`) |

## Why Use a Neon Test Branch?

- **Isolation** — Test data never pollutes the production/development branch
- **Consistency** — Test branch is forked from main, keeping the schema in sync
- **Resettable** — Reset the test branch to main at any time via Neon Console
- **Zero cost** — Neon branches are copy-on-write and consume no extra storage
