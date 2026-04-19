#!/bin/bash

set -e

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') INFO $@"
}

log "Starting tinyproxy..."
exec tinyproxy -d -c /etc/tinyproxy.conf
