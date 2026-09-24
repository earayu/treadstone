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
- `Build Sandbox Image` defaults to **verify**, which pulls an already-published
  image without building or publishing anything. Explicit **publish** mode builds
  once, loads and verifies that image, then pushes the same tested image ID.
  Publishing still requires a new immutable `vX.Y.Z` tag from `main`.
- The retired reconstructed-image workflow is no longer needed.
- `scripts/test_sandbox_image.py` checks browser/CDP, shell/WebSocket, file access,
  MCP tools, non-root execution and the absence of removed services.
- `scripts/verify-sandbox-image.sh` reuses those checks for PRs, release candidates
  and published images, including desktop/mobile UI checks, restart and container
  replacement with a persistent home volume. Files and a persistent browser
  cookie must survive both transitions. Image IDs, tool inventories, logs and
  screenshots are uploaded as Actions artifacts.

Base images use digests and coding CLI versions are explicit Dockerfile arguments,
matching the tools validated in `v0.3.0`. This does not lock every transitive
Python/npm or Debian package. The release gate tests the actual artifact, not
the assumption that two builds of the same commit are identical.

Never point Helm at an unpublished tag. Publish the image first, then update
`deploy/sandbox-runtime/values*.yaml` through a PR. Existing pods continue to use
their original image until replaced; merging code is not a production deployment.

## On-Demand Experiments

There are no schedules or automatic production deployments in these experiments.
Do not build images locally.

1. Run **Build Sandbox Image** with `mode=verify`,
   `image=ghcr.io/earayu/treadstone-sandbox:v0.3.0`, `benchmark=true`,
   `baseline=ghcr.io/earayu/treadstone-sandbox:v0.2.1`, `samples=5`.
   The two images are pulled onto independent GitHub runners, never rebuilt.
   Results include exact digests, compressed/uncompressed size, pull time,
   sequential startup/restart P50/P95, idle/active browser memory and concurrent
   startup failures. Download `sandbox-image-comparison` for raw samples and a
   Markdown summary.
2. Run **K8s E2E** with `sandbox_image` set to the published version or digest.
   Kind loads that artifact instead of rebuilding the sandbox. API/web images
   are still built on the GitHub runner. Full Hurl E2E validates control-plane
   integration and persistent lifecycle without touching production.
3. Optionally enable `benchmark=true` on **K8s E2E** for three cold-pool and
   three pre-warmed samples through the existing CLI benchmark harness. Each
   warm sample waits for a Ready Sandbox and confirms that a claim adopted it.
   For the historical AIO baseline only, set `legacy_image=true` to skip the
   new removed-service/UI contract; Hurl and benchmarks still run.

Docker restarts are not warm-pool allocations. Docker memory measurements are
cgroup working-set usage, not RSS. Kind measurements use preloaded images and
the tiny template; cold-pool timing includes replenishment but not image pulls.
Small samples on shared CI runners show direction, not production capacity or
reliable tail latency. Keep capacity experiments opt-in, outside normal PR gates.

Application releases and production deployment remain separate explicit actions;
follow the [development lifecycle](../../.agents/skills/dev-lifecycle/SKILL.md).

## Sources

`runtime/` retains the browser, terminal, shell and file implementations previously
vendored from `ghcr.io/agent-infra/sandbox:1.0.0.152`, including the OpenHands shell
implementation and GEM CDP proxy. Their existing attribution is retained.
Treadstone owns the build, startup, workspace UI and supported API surface.
Removing the AIO image dependency does not imply authorship of these components.
