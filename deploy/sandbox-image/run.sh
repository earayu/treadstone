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

export IMAGE_VERSION="${TREADSTONE_SANDBOX_VERSION}"
export OTEL_SDK_DISABLED=true
export NPM_CONFIG_PREFIX="${HOME}/.npm-global"
export PATH="${NPM_CONFIG_PREFIX}/bin:${HOME}/.local/bin:${PATH}"
export HOMEPAGE="${HOMEPAGE:-}"
export BROWSER_NO_SANDBOX="${BROWSER_NO_SANDBOX:---no-sandbox}"
export BROWSER_EXTRA_ARGS="${BROWSER_NO_SANDBOX} --lang=en-US --time-zone-for-testing=${TZ} --window-position=0,0 --window-size=${DISPLAY_WIDTH},${DISPLAY_HEIGHT} --homepage ${HOMEPAGE} ${BROWSER_EXTRA_ARGS:-}"

if [ -n "${BROWSER_USER_AGENT:-}" ]; then
  export BROWSER_EXTRA_ARGS="--user-agent=\"${BROWSER_USER_AGENT}\" ${BROWSER_EXTRA_ARGS}"
fi

mkdir -p \
  /opt/gem/nginx \
  "${LOG_DIR}" \
  "${XDG_RUNTIME_DIR}" \
  "${HOME}/.npm-global/lib" \
  "${HOME}/.config/browser/Default"
chmod 700 "${XDG_RUNTIME_DIR}"
touch "${HOME}/.Xauthority"

copy_if_missing /opt/treadstone/home-template/.bashrc "${HOME}/.bashrc"
copy_if_missing /opt/treadstone/home-template/.config/browser/Default/Preferences "${HOME}/.config/browser/Default/Preferences"

# Regenerate proxy and service configs on every start from immutable templates.
envsubst '${XDG_RUNTIME_DIR}' \
  </opt/treadstone/templates/nginx.conf.template >/opt/gem/nginx.conf
envsubst '${SANDBOX_SRV_PORT}' \
  </opt/treadstone/templates/runtime.conf.template >/opt/gem/nginx/runtime.conf

if [ -n "${PROXY_SERVER:-}" ]; then
  export BROWSER_EXTRA_ARGS="${BROWSER_EXTRA_ARGS} --proxy-server=${PROXY_SERVER}"
fi

log "Prepared rootless sandbox runtime for ${USER}"
exec /opt/gem/entrypoint.sh
