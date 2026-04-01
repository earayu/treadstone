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

echo "=== smoke-web (${APP_HOST}, ${API_HOST} -> ${RESOLVE_IP}:80) ==="

echo -n "GET http://${APP_HOST}/healthz ... "
code=$(curl -sS -o /dev/null -w "%{http_code}" \
	--resolve "${APP_HOST}:80:${RESOLVE_IP}" \
	"http://${APP_HOST}/healthz")
if [[ "$code" != "200" ]]; then
	echo "FAIL (HTTP $code)" >&2
	exit 1
fi
echo "OK"

echo -n "GET http://${APP_HOST}/ ... "
body=$(curl -sS --resolve "${APP_HOST}:80:${RESOLVE_IP}" "http://${APP_HOST}/")
if ! echo "$body" | grep -qiE '<!DOCTYPE html|<html'; then
	echo "FAIL (expected HTML shell)" >&2
	exit 1
fi
echo "OK"

echo -n "GET http://${APP_HOST}/v1/config ... "
cfg=$(curl -sS --resolve "${APP_HOST}:80:${RESOLVE_IP}" "http://${APP_HOST}/v1/config")
if ! echo "$cfg" | grep -q '"auth"'; then
	echo "FAIL (expected JSON with auth)" >&2
	exit 1
fi
echo "OK"

echo -n "GET http://${API_HOST}/health ... "
hcode=$(curl -sS -o /dev/null -w "%{http_code}" \
	--resolve "${API_HOST}:80:${RESOLVE_IP}" \
	"http://${API_HOST}/health")
if [[ "$hcode" != "200" ]]; then
	echo "FAIL (HTTP $hcode)" >&2
	exit 1
fi
echo "OK"

echo "=== smoke-web: done ==="
