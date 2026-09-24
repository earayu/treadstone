# Treadstone Sandbox Image

The maintained image is built directly from Python 3.12 / Debian Bookworm and
Node.js 22. It does not inherit an AIO or reconstructed sandbox image.

## Runtime

- Chromium with CDP, screenshots, mouse/keyboard control and noVNC handoff.
- Bash sessions over HTTP and WebSocket, file upload/download/edit APIs.
- Python runtime API with an in-process MCP adapter for browser, shell and files.
- GEM proxy for CDP and browser control.
- Python, Node.js, uv and coding CLIs available from the shell.
- UID/GID 1000 (`gem`); persistent workspaces remain at `/home/gem`.

There is no VS Code server, Jupyter, notebook kernel, separate Node execution
service, document conversion service, MCP Hub or browser MCP daemon. Run Python
and Node programs through `/v1/shell/exec`. Removed runtime routes return 404.
The existing `aio-sandbox-*` template IDs remain stable for compatibility.

## Build and Verify

All image builds run on GitHub Actions, for `linux/amd64`.

- `K8s E2E` builds the current PR image, runs the image smoke checks, then tests
  the control plane, proxy and persistent sandbox lifecycle on Kind.
- `Build Sandbox Image` publishes immutable `vX.Y.Z` tags from `main`.
- The retired reconstructed-image workflow is no longer needed.
- `scripts/test_sandbox_image.py` checks browser/CDP, shell/WebSocket, file access,
  MCP tools, non-root execution and the absence of removed services.

Never point Helm at an unpublished tag. Publish the image first, then update
`deploy/sandbox-runtime/values*.yaml` through a PR. Existing pods continue to use
their original image until replaced; merging code is not a production deployment.

## Sources

`runtime/` retains the browser, terminal, shell and file implementations previously
vendored from `ghcr.io/agent-infra/sandbox:1.0.0.152`, including the OpenHands shell
implementation and GEM CDP proxy. Their existing attribution is retained.
Treadstone owns the build, startup, workspace UI and supported API surface.
Removing the AIO image dependency does not imply authorship of these components.
