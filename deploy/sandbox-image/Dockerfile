FROM ghcr.io/agent-infra/sandbox:1.0.0.152

ARG TREADSTONE_SANDBOX_VERSION=dev
ARG CLAUDE_CODE_VERSION=latest
ARG CODEX_VERSION=latest

LABEL org.opencontainers.image.source="https://github.com/earayu/treadstone"
LABEL org.opencontainers.image.description="Treadstone Agent Sandbox"
LABEL org.opencontainers.image.version="${TREADSTONE_SANDBOX_VERSION}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV PATH="/root/.local/bin:${PATH}"

# Base image already includes Node.js, so the two npm-based coding CLIs can be
# installed directly without changing any sandbox runtime behavior.
RUN npm install -g \
    "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    "@openai/codex@${CODEX_VERSION}"

# Kimi Code CLI ships through the official installer, which installs uv when
# needed and then installs kimi-cli via uv tool into ~/.local/bin.
RUN curl -LsSf https://code.kimi.com/install.sh | bash

# Kimi installs a managed Python under `/root/.local/share/uv`, but `gem` cannot execute
# interpreters referenced via that path. Mirror the uv store to `/opt/uv` and rewrite the
# venv metadata + `python` shim used by `/usr/local/bin/kimi`.
RUN set -euo pipefail \
  && cp -a /root/.local/share/uv /opt/uv \
  && chmod -R a+rX /opt/uv \
  && sed -i 's#/root/.local/share/uv#/opt/uv#g' /usr/local/share/uv/tools/kimi-cli/pyvenv.cfg \
  && py="$(find /opt/uv/python -type f -path '*/bin/python3.13' | head -n 1)" \
  && test -n "${py}" \
  && ln -sf "${py}" /usr/local/share/uv/tools/kimi-cli/bin/python

# Cursor Agent CLI currently ships through the official installer and does not
# expose a stable versioned download URL, so this always pulls the current
# upstream release at build time.
RUN curl https://cursor.com/install -fsS | bash

# The installer places binaries under `/root/.local`, but interactive sandbox sessions
# typically run as the unprivileged `gem` user, which cannot traverse `/root` (0700).
# Mirror the install to `/opt` (world-readable) and expose `agent` / `cursor-agent` on PATH.
RUN set -euo pipefail \
  && ver_dir="$(find /root/.local/share/cursor-agent/versions -mindepth 1 -maxdepth 1 -type d | head -n 1)" \
  && ver="$(basename "${ver_dir}")" \
  && install -d -m 755 /opt/cursor-agent \
  && cp -a /root/.local/share/cursor-agent /opt/cursor-agent/share \
  && ln -sf "/opt/cursor-agent/share/versions/${ver}/cursor-agent" /usr/local/bin/cursor-agent \
  && ln -sf "/opt/cursor-agent/share/versions/${ver}/cursor-agent" /usr/local/bin/agent \
  && chmod -R a+rX /opt/cursor-agent/share

ENV TREADSTONE_SANDBOX_VERSION="${TREADSTONE_SANDBOX_VERSION}"

RUN claude --version \
    && codex --version \
    && kimi --version \
    && cursor-agent --version \
    && agent --version
