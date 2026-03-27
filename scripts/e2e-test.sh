#!/usr/bin/env bash
# E2E test runner — generates dynamic variables and invokes Hurl.
# Each .hurl file is self-contained (registers its own user), so all files
# run in parallel with no ordering dependencies.
#
# Usage:
#   make test-e2e                                  # run all tests
#   make test-e2e FILE=08-metering-admin.hurl      # run a single test file
#   make test-e2e BASE_URL=http://localhost:8000   # custom base URL
#   BASE_URL=http://localhost bash scripts/e2e-test.sh [file.hurl]

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
# Optional: pass a single filename (e.g. "08-metering-admin.hurl") to run only that file.
TARGET_FILE="${1:-}"
UNIQUE=$(head -c 8 /dev/urandom | xxd -p | head -c 8)
VARS_FILE=$(mktemp)
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
E2E_DIR="$ROOT_DIR/tests/e2e"
REPORT_DIR="$ROOT_DIR/reports/e2e"

cleanup() { rm -f "$VARS_FILE"; }
trap cleanup EXIT

TEST_PASSWORD="E2eStr0ng_Pass!"

# ── Admin credentials ─────────────────────────────────────────────────────────
# On a fresh DB the first registered user becomes ADMIN automatically.
# On a persistent DB (e.g. Kind cluster reused across runs) set these env vars
# to point at an already-admin account:
#   E2E_ADMIN_EMAIL=<email>        (required when DB has existing users)
#   E2E_ADMIN_PASSWORD=<password>  (defaults to TEST_PASSWORD if omitted)
if [ -n "${E2E_ADMIN_EMAIL:-}" ]; then
    ADMIN_EMAIL="$E2E_ADMIN_EMAIL"
    ADMIN_PASSWORD="${E2E_ADMIN_PASSWORD:-$TEST_PASSWORD}"
else
    # Fixed email (no UNIQUE suffix) so the same account is reused across runs.
    # First run on a clean DB: HTTP 201, user becomes ADMIN (first user).
    # Subsequent runs: HTTP 409, user already exists and retains ADMIN role.
    ADMIN_EMAIL="e2e-admin@test.treadstone.dev"
    ADMIN_PASSWORD="$TEST_PASSWORD"
fi

cat > "$VARS_FILE" <<EOF
base_url=${BASE_URL}
admin_email=${ADMIN_EMAIL}
admin_password=${ADMIN_PASSWORD}
email_01=e2e-01-${UNIQUE}@test.treadstone.dev
email_02=e2e-02-${UNIQUE}@test.treadstone.dev
email_03=e2e-03-${UNIQUE}@test.treadstone.dev
email_04=e2e-04-${UNIQUE}@test.treadstone.dev
email_07=e2e-07-${UNIQUE}@test.treadstone.dev
email_08=e2e-08-${UNIQUE}@test.treadstone.dev
test_password=${TEST_PASSWORD}
new_password=E2eStr0ng_New1!
unique=${UNIQUE}
EOF

# ── Wait for service ─────────────────────────────────────────────────────────

printf "Waiting for %s to be ready " "$BASE_URL"
consecutive_successes=0
for i in $(seq 1 30); do
    if curl -sf -o /dev/null "$BASE_URL/health" 2>/dev/null; then
        consecutive_successes=$((consecutive_successes + 1))
        printf "+"
        if [ "$consecutive_successes" -ge 3 ]; then
            printf " ready!\n\n"
            break
        fi
    else
        consecutive_successes=0
        printf "."
    fi
    sleep 2
    if [ "$i" -eq 30 ]; then
        printf "\nERROR: timed out after 60s waiting for 3 consecutive %s/health successes\n" "$BASE_URL"
        exit 1
    fi
done

# ── Pre-register admin user when no external admin is configured ──────────────
# Only attempt registration when E2E_ADMIN_EMAIL is not set (fresh-DB path).
# The curl exit code is intentionally ignored: on a non-fresh DB this will fail
# with 409 (user already exists), which is harmless.

if [ -z "${E2E_ADMIN_EMAIL:-}" ]; then
    # Register admin user with retry — also serves as a DB readiness gate.
    # The /health endpoint does not touch the database; a real DB-backed request
    # is needed to confirm the backend + Neon compute are fully ready.
    # Retry until we get 201 (created) or 409 (already exists — DB is up).
    printf "Pre-registering admin user (DB readiness gate) "
    for i in $(seq 1 20); do
        status=$(curl -s -o /dev/null -w "%{http_code}" \
             -X POST "${BASE_URL}/v1/auth/register" \
             -H "Content-Type: application/json" \
             -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
             2>/dev/null || echo "000")
        if [ "$status" = "201" ] || [ "$status" = "409" ]; then
            printf " ready! (HTTP %s)\n\n" "$status"
            break
        fi
        printf "."
        sleep 3
        if [ "$i" -eq 20 ]; then
            printf "\nERROR: DB not ready after 60s (last HTTP status: %s)\n" "$status"
            exit 1
        fi
    done
else
    printf "Using configured admin user: %s\n\n" "$ADMIN_EMAIL"
fi

# ── Run E2E tests (parallel by default in --test mode) ───────────────────────

mkdir -p "$REPORT_DIR"

if [ -n "$TARGET_FILE" ]; then
    printf "Running single test file: %s\n\n" "$TARGET_FILE"
    hurl --test --variables-file "$VARS_FILE" \
        --report-html "$REPORT_DIR" \
        "$E2E_DIR/$TARGET_FILE"
else
    hurl --test --variables-file "$VARS_FILE" \
        --report-html "$REPORT_DIR" \
        "$E2E_DIR"/*.hurl
fi

# ── Post-process: group by run, improve visual design ────────────────────────

python3 "$ROOT_DIR/scripts/gen-e2e-report.py" "$REPORT_DIR"

printf "\nHTML report: %s/index.html\n" "$REPORT_DIR"
