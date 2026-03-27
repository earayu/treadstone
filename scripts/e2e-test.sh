#!/usr/bin/env bash
# E2E test runner — generates dynamic variables and invokes Hurl.
# Each .hurl file is self-contained (registers its own user), so all files
# run in parallel with no ordering dependencies.
#
# Usage:
#   make test-e2e                            # default: BASE_URL=http://localhost
#   make test-e2e BASE_URL=http://localhost:8000
#   BASE_URL=http://localhost bash scripts/e2e-test.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
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
    ADMIN_EMAIL="e2e-admin-${UNIQUE}@test.treadstone.dev"
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
    curl -sf -X POST "${BASE_URL}/v1/auth/register" \
         -H "Content-Type: application/json" \
         -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
         > /dev/null || true
    printf "Admin user pre-registered (fresh-DB path): %s\n\n" "$ADMIN_EMAIL"
else
    printf "Using configured admin user: %s\n\n" "$ADMIN_EMAIL"
fi

# ── Run all E2E tests (parallel by default in --test mode) ───────────────────

mkdir -p "$REPORT_DIR"
hurl --test --variables-file "$VARS_FILE" \
    --report-html "$REPORT_DIR" \
    "$E2E_DIR"/*.hurl

# ── Post-process: group by run, improve visual design ────────────────────────

python3 "$ROOT_DIR/scripts/gen-e2e-report.py" "$REPORT_DIR"

printf "\nHTML report: %s/index.html\n" "$REPORT_DIR"
