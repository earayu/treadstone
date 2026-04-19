#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S,%3N') INFO $*"
}

copy_if_missing() {
  local src="$1"
  local dest="$2"

  if [ -e "$dest" ]; then
    return
  fi

  mkdir -p "$(dirname "$dest")"
  if [ -d "$src" ]; then
    cp -r "$src" "$dest"
  else
    cp -f "$src" "$dest"
  fi
}

export AUTOSTART_JUPYTER=$([ "${DISABLE_JUPYTER:-false}" != "true" ] && echo "true" || echo "false")
export AUTOSTART_CODE_SERVER=$([ "${DISABLE_CODE_SERVER:-false}" != "true" ] && echo "true" || echo "false")
export IMAGE_VERSION="$(cat /etc/aio_version 2>/dev/null || true)"
export OTEL_SDK_DISABLED=true
export NPM_CONFIG_PREFIX="${HOME}/.npm-global"
export PATH="${NPM_CONFIG_PREFIX}/bin:${HOME}/.local/bin:${PATH}"
export HOMEPAGE="${HOMEPAGE:-}"
export BROWSER_NO_SANDBOX="${BROWSER_NO_SANDBOX:---no-sandbox}"
export BROWSER_EXTRA_ARGS="${BROWSER_NO_SANDBOX} --lang=en-US --time-zone-for-testing=${TZ} --window-position=0,0 --window-size=${DISPLAY_WIDTH},${DISPLAY_HEIGHT} --homepage ${HOMEPAGE} ${BROWSER_EXTRA_ARGS:-}"
export TINYPROXY_CONFIG="${XDG_RUNTIME_DIR}/tinyproxy.conf"

if [ -n "${BROWSER_USER_AGENT:-}" ]; then
  export BROWSER_EXTRA_ARGS="--user-agent=\"${BROWSER_USER_AGENT}\" ${BROWSER_EXTRA_ARGS}"
fi

mkdir -p \
  "${LOG_DIR}" \
  "${XDG_RUNTIME_DIR}" \
  "${HOME}/.npm-global/lib" \
  "${HOME}/.config/browser/Default" \
  "${HOME}/.config/code-server" \
  "${HOME}/.local/share/code-server" \
  "${HOME}/.config/matplotlib"
chmod 700 "${XDG_RUNTIME_DIR}"
touch "${HOME}/.Xauthority"

copy_if_missing /opt/treadstone/home-template/.bashrc "${HOME}/.bashrc"
copy_if_missing /opt/treadstone/home-template/.config/code-server/vscode "${HOME}/.config/code-server/vscode"
copy_if_missing /opt/treadstone/home-template/.jupyter "${HOME}/.jupyter"
copy_if_missing /opt/treadstone/home-template/.config/matplotlib/matplotlibrc "${HOME}/.config/matplotlib/matplotlibrc"
copy_if_missing /opt/treadstone/home-template/.config/browser/Default/Preferences "${HOME}/.config/browser/Default/Preferences"

# Regenerate proxy and service configs on every start from immutable templates.
envsubst '${XDG_RUNTIME_DIR}' \
  </opt/treadstone/templates/nginx.conf.template >/opt/gem/nginx.conf
envsubst '${MCP_HUB_PORT} ${SANDBOX_SRV_PORT}' \
  </opt/gem/nginx/nginx.python_srv.conf >/opt/gem/nginx/python_srv.conf
envsubst '${MCP_HUB_PORT}' \
  </opt/gem/nginx/nginx.mcp_hub.conf >/opt/gem/nginx/mcp_hub.conf
envsubst '${JUPYTER_LAB_PORT}' \
  </opt/gem/nginx/nginx.jupyter_lab.conf >/opt/gem/nginx/jupyter_lab.conf
envsubst '${CODE_SERVER_PORT}' \
  </opt/gem/nginx/nginx.code_server.conf >/opt/gem/nginx/code_server.conf
envsubst '${PUBLIC_PORT}' \
  </opt/gem/nginx-server-port-proxy.conf.template >/opt/gem/nginx-server-port-proxy.conf
envsubst '${SANDBOX_SRV_PORT} ${MCP_SERVER_BROWSER_PORT} ${BROWSER_REMOTE_DEBUGGING_PORT}' \
  </opt/gem/mcp-hub.json.template >/opt/gem/mcp-hub.json

PROXY_SERVER="$(echo -n "${PROXY_SERVER:-}" | xargs)"
if [ -n "${PROXY_SERVER}" ]; then
  PROXY_SERVER=${PROXY_SERVER#\"}
  PROXY_SERVER=${PROXY_SERVER%\"}
  PROXY_SERVER=${PROXY_SERVER#http://}
  PROXY_SERVER=${PROXY_SERVER#https://}

  {
    echo "# === base.conf ==="
    envsubst '${TINYPROXY_PORT} ${XDG_RUNTIME_DIR}' </opt/gem/tinyproxy/base.conf
    echo

    if [ "${PROXY_SERVER}" != "true" ]; then
      echo "# === Auto-generated Upstream ==="
      echo "Upstream http ${PROXY_SERVER}"
      echo
    fi

    while IFS= read -r conf_file; do
      rel_path="${conf_file#/opt/gem/tinyproxy/}"
      echo "# === ${rel_path} ==="
      envsubst '${PROXY_SERVER}' <"${conf_file}"
      echo
    done < <(find /opt/gem/tinyproxy -type f -name '*.conf' ! -name 'base.conf' | sort)
  } >"${TINYPROXY_CONFIG}"

  export BROWSER_EXTRA_ARGS="${BROWSER_EXTRA_ARGS} --proxy-server=http://127.0.0.1:${TINYPROXY_PORT}"
else
  rm -f /opt/gem/supervisord/supervisord.tinyproxy.conf
fi

if [ -f /opt/aio/index.html.template ]; then
  envsubst '${DISABLE_JUPYTER},${DISABLE_CODE_SERVER}' \
    </opt/aio/index.html.template >/opt/aio/index.html
  rm -f /opt/aio/index.html.template
fi

log "Prepared rootless sandbox runtime for ${USER}"
exec /opt/gem/entrypoint.sh
