#!/usr/bin/env bash
# Smoke-test the Web UI + nginx proxy to API on Kind Ingress hosts.
# Uses curl --resolve so runner DNS does not need *.localhost resolution.
#
# Usage:
#   bash scripts/smoke-web.sh
# Optional: APP_HOST=app.localhost API_HOST=api.localhost RESOLVE_IP=127.0.0.1

set -euo pipefail

APP_HOST="${APP_HOST:-app.localhost}"
API_HOST="${API_HOST:-api.localhost}"
RESOLVE_IP="${RESOLVE_IP:-127.0.0.1}"
RETRY_ATTEMPTS="${RETRY_ATTEMPTS:-15}"
RETRY_SLEEP_SECONDS="${RETRY_SLEEP_SECONDS:-2}"

retry_until_success() {
	local description="$1"
	shift
	local attempt
	for attempt in $(seq 1 "$RETRY_ATTEMPTS"); do
		if "$@"; then
			return 0
		fi
		if [[ "$attempt" -lt "$RETRY_ATTEMPTS" ]]; then
			sleep "$RETRY_SLEEP_SECONDS"
		fi
	done
	echo "FAIL (${description})" >&2
	return 1
}

echo "=== smoke-web (${APP_HOST}, ${API_HOST} -> ${RESOLVE_IP}:80) ==="

echo -n "GET http://${APP_HOST}/healthz ... "
retry_until_success "expected HTTP 200 from ${APP_HOST}/healthz" bash -lc '
	code=$(curl -sS -o /dev/null -w "%{http_code}" \
		--resolve "'"${APP_HOST}:80:${RESOLVE_IP}"'" \
		"http://'"${APP_HOST}"'/healthz")
	[[ "$code" == "200" ]]
'
echo "OK"

echo -n "GET http://${APP_HOST}/ ... "
retry_until_success "expected HTML shell from ${APP_HOST}/" bash -lc '
	body=$(curl -sS --resolve "'"${APP_HOST}:80:${RESOLVE_IP}"'" "http://'"${APP_HOST}"'/")
	echo "$body" | grep -qiE "<!DOCTYPE html|<html"
'
echo "OK"

echo -n "GET http://${APP_HOST}/v1/config ... "
retry_until_success "expected auth config JSON from ${APP_HOST}/v1/config" bash -lc '
	cfg=$(curl -sS --resolve "'"${APP_HOST}:80:${RESOLVE_IP}"'" "http://'"${APP_HOST}"'/v1/config")
	echo "$cfg" | grep -q "\"auth\""
'
echo "OK"

echo -n "GET http://${API_HOST}/health ... "
retry_until_success "expected HTTP 200 from ${API_HOST}/health" bash -lc '
	hcode=$(curl -sS -o /dev/null -w "%{http_code}" \
		--resolve "'"${API_HOST}:80:${RESOLVE_IP}"'" \
		"http://'"${API_HOST}"'/health")
	[[ "$hcode" == "200" ]]
'
echo "OK"

echo "=== smoke-web: done ==="
