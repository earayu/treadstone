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

cat > "$VARS_FILE" <<EOF
base_url=${BASE_URL}
email_01=e2e-01-${UNIQUE}@test.treadstone.dev
email_02=e2e-02-${UNIQUE}@test.treadstone.dev
email_03=e2e-03-${UNIQUE}@test.treadstone.dev
email_04=e2e-04-${UNIQUE}@test.treadstone.dev
test_password=E2eStr0ng_Pass!
new_password=E2eStr0ng_New1!
unique=${UNIQUE}
EOF

# ── Wait for service ─────────────────────────────────────────────────────────

printf "Waiting for %s to be ready " "$BASE_URL"
for i in $(seq 1 30); do
    if curl -sf -o /dev/null "$BASE_URL/health" 2>/dev/null; then
        printf " ready!\n\n"
        break
    fi
    printf "."
    sleep 2
    if [ "$i" -eq 30 ]; then
        printf "\nERROR: timed out after 60s waiting for %s/health\n" "$BASE_URL"
        exit 1
    fi
done

# ── Run all E2E tests (parallel by default in --test mode) ───────────────────

mkdir -p "$REPORT_DIR"
hurl --test --variables-file "$VARS_FILE" \
    --report-html "$REPORT_DIR" \
    "$E2E_DIR"/*.hurl

printf "\nHTML report: %s/index.html\n" "$REPORT_DIR"
