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

# Cursor Agent CLI currently ships through the official installer and does not
# expose a stable versioned download URL, so this always pulls the current
# upstream release at build time.
RUN curl https://cursor.com/install -fsS | bash

ENV TREADSTONE_SANDBOX_VERSION="${TREADSTONE_SANDBOX_VERSION}"

RUN claude --version \
    && codex --version \
    && kimi --version \
    && cursor-agent --version
