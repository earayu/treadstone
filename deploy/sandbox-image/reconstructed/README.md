# Reconstructed `agent-infra/sandbox` Image

This directory contains a best-effort reconstruction of `ghcr.io/agent-infra/sandbox:1.0.0.152`.

It is intentionally separate from the existing `deploy/sandbox-image/Dockerfile`, which builds the Treadstone add-on layer **on top of** the upstream image. This reconstruction tries to rebuild the upstream sandbox behavior from `ubuntu:22.04` plus:

- runtime scripts and templates extracted from the published image
- public download URLs recoverable from image history
- package metadata recoverable from the live container

## Scope

- Goal: get close enough to build, inspect, and iterate on an upstream-equivalent image
- Non-goal: guarantee byte-for-byte reproduction of the original private Dockerfile

## Layout

- `Dockerfile` — best-effort reconstructed build
- `requirements-python-runtime.txt` — minimum Python runtime needed by the recovered `python-server`
- `runtime/` — small runtime assets copied from the published image (`/opt/gem`, `/opt/gem-server`, `/opt/aio`, `/opt/terminal`, extracted `python-server` package code)

## Current limitation

- The reconstructed build is currently pinned to `linux/amd64`.
- The exact Chromium 133 artifact used by upstream was confirmed for `amd64`; an equivalent `linux/arm64` artifact was not recovered during this round.

## Local build

```bash
export https_proxy=http://127.0.0.1:8118
export http_proxy=http://127.0.0.1:8118

docker buildx build \
  --load \
  --platform linux/amd64 \
  -f deploy/sandbox-image/reconstructed/Dockerfile \
  -t treadstone-sandbox-reconstructed:test \
  deploy/sandbox-image/reconstructed
```

## Publish workflow

Use `.github/workflows/sandbox-image-reconstructed.yml`.

- Release tag prefix: `sandbox-reconstructed-v*`
- Output image: `ghcr.io/<owner>/treadstone-sandbox-reconstructed`
- The workflow only publishes a new semver once and only allows manual release from `main`
