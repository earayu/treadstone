#!/bin/bash

set -e

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') INFO $@"
}

CONFIG_PATH="${TINYPROXY_CONFIG:-${XDG_RUNTIME_DIR}/tinyproxy.conf}"

log "Starting tinyproxy with ${CONFIG_PATH}..."
exec tinyproxy -d -c "${CONFIG_PATH}"
