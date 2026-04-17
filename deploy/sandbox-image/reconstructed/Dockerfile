FROM ubuntu:22.04

ARG TARGETARCH
ARG VERSION=1.0.0.152
ARG NODEJS_SETUP_URL=https://deb.nodesource.com/setup_22.x
ARG CODE_SERVER_VERSION=4.104.0
ARG MCP_HUB_VERSION=1.1.0
ARG MCP_SERVER_BROWSER_VERSION=1.2.21
ARG CHROME_DEVTOOLS_MCP_VERSION=0.9.0
ARG JUPYTER_CLIENT_VERSION=8.6.3
ARG IPYKERNEL_VERSION=7.1.0
ARG NOVNC_URL=https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip
ARG WEBSOCAT_VERSION=v1.13.0
ARG CHROMIUM_VERSION=133.0.6943.16
ARG CHROMIUM_ZIP_AMD64=https://storage.googleapis.com/chrome-for-testing-public/133.0.6943.16/linux64/chrome-linux64.zip
ARG PYTHON_3_11_URL_AMD64=https://github.com/astral-sh/python-build-standalone/releases/download/20250723/cpython-3.11.13+20250723-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
ARG PYTHON_3_12_URL_AMD64=https://github.com/astral-sh/python-build-standalone/releases/download/20250723/cpython-3.12.11+20250723-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz

LABEL org.opencontainers.image.source="https://github.com/earayu/treadstone"
LABEL org.opencontainers.image.description="Best-effort reconstruction of ghcr.io/agent-infra/sandbox:1.0.0.152"
LABEL org.opencontainers.image.version="${VERSION}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
ENV USER=gem USER_UID=1000 USER_GID=1000
ENV DISPLAY=:99.0 DISPLAY_WIDTH=1280 DISPLAY_HEIGHT=1024 DISPLAY_DEPTH=24
ENV XDG_RUNTIME_DIR=/tmp/runtime-gem
ENV BROWSER_EXECUTABLE_PATH=/usr/local/bin/browser
ENV BROWSER_REMOTE_DEBUGGING_PORT=9222
ENV BROWSER_COMMANDLINE_ARGS="--disable-backgrounding-occluded-windows     --disable-background-timer-throttling     --disable-blink-features=AutomationControlled     --disable-dev-shm-usage     --disable-external-intent-requests     --disable-features=IPH_DesktopCustomizeChrome,IsolateOrigins,site-per-proces,Translate     --disable-focus-on-load     --disable-gpu     --disable-infobars     --disable-popup-blocking     --disable-prompt-on-repost     --disable-renderer-backgrounding     --disable-site-isolation-trials     --disable-web-security     --disable-window-activation     --mute-audio     --no-default-browser-check     --no-first-run     --noerrdialogs     --remote-allow-origins=*     --remote-debugging-port=9222     --suppress-message-center-popups     --start-maximized"
ENV BROWSER_EXTRA_ARGS=
ENV DNS_OVER_HTTPS_TEMPLATES=
ENV LOG_DIR=/var/log/gem
ENV JWT_PUBLIC_KEY=
ENV VNC_SERVER_PORT=5900
ENV WEBSOCKET_PROXY_PORT=6080
ENV GEM_SERVER_PORT=8088
ENV MCP_SERVER_PORT=8089
ENV PUBLIC_PORT=8080
ENV AUTH_BACKEND_PORT=8081
ENV WAIT_PORTS=8091,8079
ENV WAIT_TIMEOUT=300
ENV WAIT_INTERVAL=0.25
ENV MCP_HUB_PORT=8079
ENV SANDBOX_SRV_PORT=8091
ENV JUPYTER_LAB_PORT=8888
ENV CODE_SERVER_PORT=8200
ENV MCP_SERVER_BROWSER_PORT=8100
ENV TINYPROXY_PORT=8118
ENV MAX_SHELL_SESSIONS=50
ENV LANG=en_US.UTF-8 TZ=Asia/Singapore LANGUAGE=en_US:en LC_ALL=en_US.UTF-8
ENV PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/browser
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV BROWSER_NO_SANDBOX=
ENV BROWSER_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
ENV UV_TOOL_BIN_DIR=/usr/local/bin/
ENV UV_TOOL_DIR=/usr/local/share/uv/tools
ENV DISABLE_JUPYTER=false
ENV DISABLE_CODE_SERVER=false

RUN if [ "${TARGETARCH:-amd64}" != "amd64" ]; then \
      echo "This reconstruction is currently validated only for linux/amd64." >&2; \
      exit 1; \
    fi

RUN set -eux; \
  for attempt in 1 2 3; do \
    if \
      apt-get update -o Acquire::Retries=5 && \
      apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
        ca-certificates \
        curl \
        wget \
        git \
        jq \
        unzip \
        zip \
        gnupg \
        gettext-base \
        locales \
        sudo \
        supervisor \
        nginx \
        openbox \
        tigervnc-standalone-server \
        tinyproxy \
        netcat-openbsd \
        xvfb \
        xauth \
        dbus-x11 \
        tmux \
        ffmpeg \
        imagemagick \
        build-essential \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-venv \
        python3-tk \
        scrot \
        xclip \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcairo2 \
        libcups2 \
        libdrm2 \
        libgbm1 \
        libglib2.0-0 \
        libgtk-3-0 \
        libnss3 \
        libnspr4 \
        libpango-1.0-0 \
        libu2f-udev \
        libvulkan1 \
        libx11-6 \
        libx11-xcb1 \
        libxcb-dri3-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
        libxshmfence1 \
        fonts-liberation \
        fonts-noto-color-emoji \
        fonts-wqy-zenhei; \
    then \
      break; \
    fi; \
    if [ "$attempt" -eq 3 ]; then \
      exit 1; \
    fi; \
    rm -rf /var/lib/apt/lists/*; \
    sleep 5; \
  done; \
  sed -i 's/^# *en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen; \
  locale-gen; \
  update-ca-certificates; \
  rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "${NODEJS_SETUP_URL}" | bash - \
  && apt-get update \
  && apt-get install -y --no-install-recommends nodejs \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
  && ln -sf /root/.local/bin/uv /usr/local/bin/uv \
  && ln -sf /root/.local/bin/uvx /usr/local/bin/uvx

RUN mkdir -p /opt/python3.11 /opt/python3.12 \
  && curl -fsSL "${PYTHON_3_11_URL_AMD64}" | tar -xz --strip-components=1 -C /opt/python3.11 \
  && curl -fsSL "${PYTHON_3_12_URL_AMD64}" | tar -xz --strip-components=1 -C /opt/python3.12 \
  && /opt/python3.12/bin/python3.12 -m ensurepip --upgrade

COPY requirements-python-runtime.txt /tmp/requirements-python-runtime.txt

RUN /opt/python3.12/bin/pip3.12 install --no-cache-dir -r /tmp/requirements-python-runtime.txt

RUN mkdir -p /opt/browser /opt/runtime/nodejs /opt/jupyter/runtime /opt/jupyter/data /opt/aio /opt/terminal /etc/browser/policies/managed

RUN curl -fsSL "${CHROMIUM_ZIP_AMD64}" -o /tmp/chrome-linux64.zip \
  && unzip -q /tmp/chrome-linux64.zip -d /opt/browser \
  && mv /opt/browser/chrome-linux64 /opt/browser/current \
  && ln -sf /opt/browser/current/chrome /opt/browser/chrome \
  && ln -sf /opt/browser/chrome /etc/alternatives/browser \
  && ln -sf /etc/alternatives/browser /usr/local/bin/browser \
  && rm -f /tmp/chrome-linux64.zip

RUN curl -fsSL "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server-${CODE_SERVER_VERSION}-linux-amd64.tar.gz" \
      -o /tmp/code-server.tar.gz \
  && tar -xzf /tmp/code-server.tar.gz -C /tmp \
  && mv "/tmp/code-server-${CODE_SERVER_VERSION}-linux-amd64" /opt/runtime/code-server \
  && ln -sf /opt/runtime/code-server/bin/code-server /usr/bin/code-server \
  && rm -f /tmp/code-server.tar.gz

RUN curl -fsSL "${NOVNC_URL}" -o /tmp/novnc.zip \
  && unzip -q /tmp/novnc.zip -d /opt \
  && mv /opt/noVNC-1.4.0 /opt/novnc \
  && rm -f /tmp/novnc.zip

RUN curl -fsSL "https://github.com/vi/websocat/releases/download/${WEBSOCAT_VERSION}/websocat.x86_64-unknown-linux-musl" \
      -o /usr/local/bin/websocat \
  && chmod +x /usr/local/bin/websocat

RUN npm install -g \
    "@agent-infra/mcp-hub@${MCP_HUB_VERSION}" \
    "@agent-infra/mcp-server-browser@${MCP_SERVER_BROWSER_VERSION}" \
    "chrome-devtools-mcp@${CHROME_DEVTOOLS_MCP_VERSION}"

COPY runtime/ /

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
  && python3 -m pip install --no-cache-dir /opt/gem-server \
  && python3 -m pip install --no-cache-dir "jupyter-client==${JUPYTER_CLIENT_VERSION}" "ipykernel==${IPYKERNEL_VERSION}" \
  && /opt/python3.11/bin/python -m pip install --no-cache-dir "jupyter-client==${JUPYTER_CLIENT_VERSION}" "ipykernel==${IPYKERNEL_VERSION}" \
  && ln -sf /usr/bin/python3 /usr/local/bin/python \
  && python3 -m ipykernel install --prefix /usr/local --name python3.10 --display-name "Python 3.10" \
  && python3 -m ipykernel install --prefix /usr/local --name python3 --display-name "Python 3 (ipykernel)" \
  && /opt/python3.11/bin/python -m ipykernel install --prefix /usr/local --name python3.11 --display-name "Python 3.11"

RUN python3 - <<'PY'
import json
from pathlib import Path

specs = {
    "python3.10": {
        "argv": ["/usr/bin/python3.10", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Python 3.10",
        "language": "python",
        "metadata": {"debugger": True},
    },
    "python3": {
        "argv": ["python", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Python 3 (ipykernel)",
        "language": "python",
        "metadata": {"debugger": True},
    },
    "python3.11": {
        "argv": ["/opt/python3.11/bin/python", "-Xfrozen_modules=off", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Python 3.11",
        "language": "python",
        "metadata": {"debugger": True},
    },
}

base = Path("/usr/local/share/jupyter/kernels")
for name, spec in specs.items():
    path = base / name / "kernel.json"
    path.write_text(json.dumps(spec, indent=1) + "\n")
PY
RUN mkdir -p /opt/python3.12/lib/python3.12/site-packages \
  && if [ -d /opt/python3.12/site-packages ]; then cp -a /opt/python3.12/site-packages/. /opt/python3.12/lib/python3.12/site-packages/; fi \
  && printf '%s\n' \
    '#!/usr/bin/python3' \
    'import sys' \
    'from gem.cli import cli' \
    "if __name__ == '__main__':" \
    "    if sys.argv[0].endswith('.exe'):" \
    "        sys.argv[0] = sys.argv[0][:-4]" \
    '    sys.exit(cli())' \
    > /usr/local/bin/gem-server \
  && chmod +x /usr/local/bin/gem-server \
  && printf '%s\n' \
    '#!/opt/python3.12/bin/python3.12' \
    'import re' \
    'import sys' \
    'from app.cli import cli' \
    "if __name__ == '__main__':" \
    "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])" \
    '    sys.exit(cli())' \
    > /usr/local/bin/python-server \
  && chmod +x /usr/local/bin/python-server \
  && shopt -s nullglob \
  && executables=( \
    /opt/gem/*.sh \
    /opt/gem/run.sh \
    /opt/gem/entrypoint.sh \
    /opt/gem/xdg-settings \
    /opt/gem-server/gem-server \
    /opt/python3.12/lib/python3.12/site-packages/app/scripts/*.sh \
  ) \
  && if [ "${#executables[@]}" -gt 0 ]; then chmod +x "${executables[@]}"; fi \
  && chmod -R a+rX /opt/gem /opt/gem-server /opt/aio /opt/terminal /opt/application /opt/python3.12/lib/python3.12/site-packages/app /opt/python3.12/lib/python3.12/site-packages/vendors

RUN printf '%s\n' "${VERSION}" > /etc/aio_version

ENTRYPOINT ["/opt/gem/run.sh"]
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=8 CMD /bin/bash -lc 'nc -z localhost "${BROWSER_REMOTE_DEBUGGING_PORT}" || exit 1'
