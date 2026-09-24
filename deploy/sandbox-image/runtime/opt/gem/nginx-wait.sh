#!/usr/bin/env bash
set -euo pipefail

deadline=$((SECONDS + 180))
until curl -fsS "http://127.0.0.1:${SANDBOX_SRV_PORT}/health" >/dev/null \
   && curl -fsS "http://127.0.0.1:${BROWSER_REMOTE_DEBUGGING_PORT}/json/version" >/dev/null \
   && nc -z 127.0.0.1 "${GEM_SERVER_PORT}" \
   && nc -z 127.0.0.1 "${WEBSOCKET_PROXY_PORT}"; do
  if ((SECONDS >= deadline)); then
    echo "Timed out waiting for browser and shell runtime" >&2
    exit 1
  fi
  sleep 1
done
exec /usr/sbin/nginx -c /opt/gem/nginx.conf -g 'daemon off;'
