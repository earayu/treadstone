#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') INFO $*"
}

log "Starting rootless entrypoint..."

mkdir -p "${LOG_DIR}" "${XDG_RUNTIME_DIR}" /var/lib/nginx /tmp/.X11-unix
chmod 700 "${XDG_RUNTIME_DIR}"
chmod 1777 /tmp/.X11-unix

mkdir -p "${HOME}/.config/browser/Default"
if [ ! -f "${HOME}/.config/browser/Default/Preferences" ]; then
  cp "/opt/gem/preferences.json" "${HOME}/.config/browser/Default/Preferences"
fi

TRIMMED_DOH_TEMPLATES="$(echo -n "${DNS_OVER_HTTPS_TEMPLATES:-}" | xargs)"
if [ -n "${TRIMMED_DOH_TEMPLATES}" ]; then
  cat >/etc/browser/policies/managed/dns_over_https.json <<EOF
{
  "DnsOverHttpsMode": "secure",
  "DnsOverHttpsTemplates": "${TRIMMED_DOH_TEMPLATES}"
}
EOF
else
  rm -f /etc/browser/policies/managed/dns_over_https.json
fi

AUTH_CONFIG="/opt/gem/nginx-server-with-auth.conf"
NO_AUTH_CONFIG="/opt/gem/nginx-server-without-auth.conf"
ACTIVE_CONFIG="/opt/gem/nginx-server-active.conf"

TRIMMED_JWT_PUBLIC_KEY="$(echo -n "${JWT_PUBLIC_KEY:-}" | xargs)"
if [ -n "${TRIMMED_JWT_PUBLIC_KEY}" ]; then
  envsubst '${PUBLIC_PORT} ${AUTH_BACKEND_PORT} ${GEM_SERVER_PORT}' \
    <"${AUTH_CONFIG}" >"${ACTIVE_CONFIG}"
else
  envsubst '${PUBLIC_PORT}' \
    <"${NO_AUTH_CONFIG}" >"${ACTIVE_CONFIG}"
fi

envsubst '${BROWSER_REMOTE_DEBUGGING_PORT}' </opt/gem/nginx.legacy.conf >/opt/gem/nginx/legacy.conf
envsubst '${GEM_SERVER_PORT}' </opt/gem/nginx.srv.conf >/opt/gem/nginx/srv.conf
envsubst '${WEBSOCKET_PROXY_PORT}' </opt/gem/nginx.vnc.conf >/opt/gem/nginx/vnc.conf

if [ ! -f /opt/gem/mcp.disabled ]; then
  envsubst '${MCP_SERVER_PORT}' </opt/gem/nginx.mcp.conf >/opt/gem/nginx/mcp.conf
else
  rm -f /opt/gem/nginx/mcp.conf
fi

log "Starting supervisord as ${USER}..."
exec /usr/bin/supervisord -n -c /opt/gem/supervisord.conf
