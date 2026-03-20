#!/usr/bin/env bash
# E2E test runner — generates dynamic variables and invokes Hurl.
#
# Usage:
#   make test-e2e                            # default: BASE_URL=http://localhost
#   make test-e2e BASE_URL=http://localhost:8000
#   BASE_URL=http://localhost bash scripts/e2e-test.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
UNIQUE=$(head -c 8 /dev/urandom | xxd -p | head -c 8)
VARS_FILE=$(mktemp)
REPORT_DIR=$(mktemp -d)
E2E_DIR="$(cd "$(dirname "$0")/.." && pwd)/tests/e2e"

cleanup() { rm -f "$VARS_FILE"; rm -rf "$REPORT_DIR"; }
trap cleanup EXIT

cat > "$VARS_FILE" <<EOF
base_url=${BASE_URL}
test_email=e2e-${UNIQUE}@test.treadstone.dev
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

# ── Phase 1: Register user (sequential, captures user_id) ───────────────────

hurl --test --report-json "$REPORT_DIR" --variables-file "$VARS_FILE" \
    "$E2E_DIR/01-auth-flow.hurl"

USER_ID=$(python3 -c "
import json, sys
data = json.load(open('$REPORT_DIR/report.json'))
for item in data:
    for entry in item.get('entries', []):
        for cap in entry.get('captures', []):
            if cap.get('name') == 'user_id':
                print(cap['value']); sys.exit(0)
print('')
" 2>/dev/null || echo "")

if [ -n "$USER_ID" ]; then
    echo "user_id=${USER_ID}" >> "$VARS_FILE"
fi

# ── Phase 2: API key + sandbox tests (parallel-safe, same password) ──────────

hurl --test --variables-file "$VARS_FILE" \
    "$E2E_DIR/02-api-key.hurl" \
    "$E2E_DIR/03-sandbox-crud.hurl"

# ── Phase 3: Password change + cleanup (sequential, mutates password) ────────

hurl --test --jobs 1 --variables-file "$VARS_FILE" \
    "$E2E_DIR/04-password-change.hurl" \
    "$E2E_DIR/05-cleanup.hurl"
