# Integration Tests

Integration tests run against real PostgreSQL. Use an isolated test database,
never a shared development or production database.

## Quick Start

```bash
docker run -d --rm --name treadstone-test-postgres \
  -p 127.0.0.1:55432:5432 \
  -e POSTGRES_USER=treadstone -e POSTGRES_PASSWORD=treadstone \
  -e POSTGRES_DB=treadstone_test postgres:16
docker exec treadstone-test-postgres pg_isready -U treadstone -d treadstone_test
export TREADSTONE_DATABASE_URL=postgresql+asyncpg://treadstone:treadstone@localhost:55432/treadstone_test
make migrate
make test-integration
docker stop treadstone-test-postgres
```

Wait for `pg_isready` to report accepting connections before running migrations.
The container and its data are disposable. These credentials are only for local
testing; use TLS (`?sslmode=require`) for remote databases.

## Connection Configuration

Alternatively, copy `tests/integration/.env.test.example` to
`tests/integration/.env.test` and set the test database URL there.
This file is gitignored. The integration fixture uses its URL when present;
otherwise it uses the application settings, including `TREADSTONE_DATABASE_URL`.

`make migrate` does not read `.env.test`. Export the same URL explicitly before
running migrations. Avoid keeping a stale `.env.test` pointing at another database.

CI starts a fresh PostgreSQL service container, applies all Alembic migrations,
and runs the integration suite without external database credentials.

## Running

```bash
make test-integration  # Real database tests only
make test-all          # Unit, API, and integration tests
```

The fixture rebuilds the async engine for each test. Auth tests use unique email
prefixes and clean up their own data.

## Test Inventory

| Test | What it verifies |
|------|-----------------|
| `test_tables_exist` | Alembic migration correctly created user/oauth_account/api_key tables and removed invitation |
| `test_register_creates_user_in_db` | Register API creates a user record in the real DB |
| `test_full_auth_flow` | Full flow: register → login → get user → change password → login with new password |
| `test_duplicate_register_returns_409` | Duplicate email registration returns 409 Conflict |
| `test_config_endpoint_returns_auth_info` | `/v1/config` returns correct auth configuration |
| `test_postgres_connection_and_version` | Connectivity and PostgreSQL version using the selected test database |
