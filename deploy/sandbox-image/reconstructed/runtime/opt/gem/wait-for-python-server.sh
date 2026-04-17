#!/usr/bin/env bash

set -euo pipefail

if [[ ${FASTAPI_WAIT_SKIP:-0} != 0 ]]; then
  exec "$@"
fi

if [[ $# -lt 1 ]]; then
  echo "wait-for-python-server: missing command to execute" >&2
  exit 64
fi

host=${FASTAPI_WAIT_HOST:-127.0.0.1}
port=${SANDBOX_SRV_PORT:--8091}
path=${FASTAPI_WAIT_PATH:-/health}
timeout=${FASTAPI_WAIT_TIMEOUT:-10}
interval=${FASTAPI_WAIT_INTERVAL:-1}

if [[ -z "$port" ]]; then
  echo "wait-for-python-server: SANDBOX_SRV_PORT is not set" >&2
  exit 65
fi

start_ts=$(date +%s)
echo "$(date '+%Y-%m-%d %H:%M:%S') - wait-for-python-server: waiting for FastAPI at http://${host}:${port}${path}"

while true; do
  if curl --silent --fail --max-time 2 "http://${host}:${port}${path}" >/dev/null; then
    elapsed=$(( $(date +%s) - start_ts ))
    echo "$(date '+%Y-%m-%d %H:%M:%S') - wait-for-python-server: FastAPI is ready after ${elapsed}s"
    break
  fi

  elapsed=$(( $(date +%s) - start_ts ))
  if (( elapsed >= timeout )); then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - wait-for-python-server: timeout after ${timeout}s waiting for FastAPI" >&2
    exit 111
  fi

  sleep "$interval"
done

exec "$@"
