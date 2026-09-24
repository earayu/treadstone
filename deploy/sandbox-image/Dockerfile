FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS node
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ARG TARGETARCH
ARG TREADSTONE_SANDBOX_VERSION=dev
ARG CHROMIUM_VERSION=154.0.8037.57
ARG NOVNC_VERSION=1.6.0
ARG WEBSOCAT_VERSION=v1.13.0
ARG CLAUDE_CODE_VERSION=2.1.281
ARG CODEX_VERSION=0.156.1
ARG KIMI_CLI_VERSION=1.52.0
ARG CURSOR_AGENT_VERSION=2026.09.23-86fc751

LABEL org.opencontainers.image.source="https://github.com/earayu/treadstone"
LABEL org.opencontainers.image.description="Treadstone browser and shell sandbox"
LABEL org.opencontainers.image.version="${TREADSTONE_SANDBOX_VERSION}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    USER=gem USER_UID=1000 USER_GID=1000 HOME=/home/gem \
    DISPLAY=:99.0 DISPLAY_WIDTH=1280 DISPLAY_HEIGHT=1024 DISPLAY_DEPTH=24 XDG_SESSION_TYPE=x11 \
    XDG_RUNTIME_DIR=/tmp/runtime-gem LOG_DIR=/tmp/treadstone/log \
    BROWSER_EXECUTABLE_PATH=/usr/local/bin/browser BROWSER_REMOTE_DEBUGGING_PORT=9222 \
    BROWSER_COMMANDLINE_ARGS="--disable-backgrounding-occluded-windows --disable-background-timer-throttling --disable-dev-shm-usage --disable-gpu --no-default-browser-check --no-first-run --remote-allow-origins=* --remote-debugging-port=9222 --start-maximized" \
    BROWSER_EXTRA_ARGS="" BROWSER_NO_SANDBOX=--no-sandbox \
    DNS_OVER_HTTPS_TEMPLATES="" JWT_PUBLIC_KEY="" \
    VNC_SERVER_PORT=5900 WEBSOCKET_PROXY_PORT=6080 GEM_SERVER_PORT=8088 \
    PUBLIC_PORT=8080 AUTH_BACKEND_PORT=8081 SANDBOX_SRV_PORT=8091 \
    MAX_SHELL_SESSIONS=50 WORKSPACE=/home/gem \
    LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8 TZ=Etc/UTC \
    UV_TOOL_BIN_DIR=/usr/local/bin UV_TOOL_DIR=/usr/local/share/uv/tools \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    PYTHONPATH=/opt/treadstone/python \
    TREADSTONE_SANDBOX_VERSION="${TREADSTONE_SANDBOX_VERSION}"

RUN test "${TARGETARCH:-amd64}" = amd64
RUN apt-get update -o Acquire::Retries=5 \
    && apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
       ca-certificates curl wget git jq unzip zip gettext-base locales \
       supervisor nginx openbox tigervnc-standalone-server netcat-openbsd \
       xauth dbus-x11 tmux scrot xclip x11-xserver-utils xdg-utils procps \
       build-essential pkg-config ripgrep vim-tiny nano tree rsync \
       libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 libdrm2 \
       libgbm1 libglib2.0-0 libgtk-3-0 libnss3 libnspr4 libpango-1.0-0 libtk8.6 \
       libx11-6 libx11-xcb1 libxcb-dri3-0 libxcomposite1 libxdamage1 \
       libxfixes3 libxkbcommon0 libxrandr2 libxshmfence1 \
       fonts-liberation fonts-noto-color-emoji fonts-wqy-zenhei \
    && sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen && rm -rf /var/lib/apt/lists/* \
    && python -c 'import tkinter'

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY requirements-python-runtime.txt /tmp/requirements-python-runtime.txt
RUN pip install --no-cache-dir -r /tmp/requirements-python-runtime.txt

RUN curl --retry 5 -fsSL \
      "https://storage.googleapis.com/chrome-for-testing-public/${CHROMIUM_VERSION}/linux64/chrome-linux64.zip" \
      -o /tmp/browser.zip \
    && unzip -q /tmp/browser.zip -d /opt \
    && ln -s /opt/chrome-linux64/chrome /usr/local/bin/browser \
    && rm /tmp/browser.zip \
    && curl --retry 5 -fsSL "https://github.com/novnc/noVNC/archive/refs/tags/v${NOVNC_VERSION}.zip" -o /tmp/novnc.zip \
    && unzip -q /tmp/novnc.zip -d /opt \
    && mv "/opt/noVNC-${NOVNC_VERSION}" /opt/novnc \
    && ln -s vnc.html /opt/novnc/index.html \
    && rm /tmp/novnc.zip \
    && curl --retry 5 -fsSL \
      "https://github.com/vi/websocat/releases/download/${WEBSOCAT_VERSION}/websocat.x86_64-unknown-linux-musl" \
      -o /usr/local/bin/websocat \
    && chmod 755 /usr/local/bin/websocat

# Coding CLIs are shell tools, not additional background services.
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" "@openai/codex@${CODEX_VERSION}" \
    && mkdir -p /opt/uv \
    && uv tool install "kimi-cli==${KIMI_CLI_VERSION}" \
    && chmod -R a+rX /opt/uv /usr/local/share/uv
RUN install -d "/opt/cursor-agent/${CURSOR_AGENT_VERSION}" \
    && curl --retry 5 -fsSL \
       "https://downloads.cursor.com/lab/${CURSOR_AGENT_VERSION}/linux/x64/agent-cli-package.tar.gz" \
       | tar --strip-components=1 -xz -C "/opt/cursor-agent/${CURSOR_AGENT_VERSION}" \
    && ln -s "/opt/cursor-agent/${CURSOR_AGENT_VERSION}/cursor-agent" /usr/local/bin/cursor-agent \
    && ln -s "/opt/cursor-agent/${CURSOR_AGENT_VERSION}/cursor-agent" /usr/local/bin/agent \
    && chmod -R a+rX /opt/cursor-agent

COPY runtime/ /
RUN pip install --no-cache-dir /opt/gem-server
RUN curl --retry 5 -fsSL https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css -o /opt/terminal/xterm.css \
    && curl --retry 5 -fsSL https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js -o /opt/terminal/xterm.js \
    && curl --retry 5 -fsSL https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js -o /opt/terminal/xterm-addon-fit.js
COPY run.sh entrypoint.sh /opt/gem/
COPY supervisord.conf /opt/gem/supervisord.conf
COPY nginx.conf.template /opt/treadstone/templates/nginx.conf.template

# Seed empty PVCs without overwriting user data on subsequent starts.
RUN groupadd --gid 1000 gem \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home gem \
    && install -d /opt/treadstone/home-template/.config/browser/Default \
       /etc/browser/policies/managed /var/log/nginx /var/lib/nginx \
    && cp /opt/gem/bashrc /opt/treadstone/home-template/.bashrc \
    && cp /opt/gem/preferences.json /opt/treadstone/home-template/.config/browser/Default/Preferences \
    && chmod 755 /opt/gem/*.sh /opt/treadstone/python/app/scripts/*.sh \
    && chown -R gem:gem /home/gem /opt/gem /opt/treadstone \
       /etc/browser/policies/managed /var/log/nginx /var/lib/nginx

ENV PATH="/home/gem/.npm-global/bin:/home/gem/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
USER gem
WORKDIR /home/gem
RUN claude --version && codex --version && kimi --version && cursor-agent --version
ENTRYPOINT ["/opt/gem/run.sh"]
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=8 CMD curl -fsS http://127.0.0.1:8080/health || exit 1
