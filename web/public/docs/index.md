# Overview

Treadstone is **agent-native sandbox infrastructure**: a hosted control plane so agents can spin up isolated environments, run code and tools, use the browser, and bring a human in only when the workflow needs one—without you hand-wiring auth, lifecycle, or routing for every run.

That is the same bet as the product home page: sandboxes for agents that do not wait on humans for the mechanics—only for judgement when it matters. A raw container is not an agent platform. The runtime matters, but so does everything around it: stable interfaces, identity, lifecycle, scoped access, and plan limits. Treadstone packages that into a service so agents can call it directly and manage sandboxes on their own.

Over HTTP there are **two surfaces**, not one: **control plane** calls (`/v1/...` on the API host) manage Treadstone itself; **data plane** calls use the per-sandbox **`urls.proxy`** link — a reverse proxy that strips the proxy routing prefix and forwards the request to the HTTP server **inside** the container. See [REST API Guide](/docs/rest-api-guide.md) for how this maps to paths, auth, and OpenAPI.

## What The Platform Gives You

- **Three interfaces, one contract**: CLI, Python SDK, and REST API with consistent resources and JSON-shaped responses—so exploration, automation, and integrations stay aligned.
- **Orchestration and lifecycle**: Create, inspect, start, stop, and delete sandboxes on demand; reuse or retire environments as the agent’s task changes.
- **Templates that match your plan**: Discover CPU, memory, and persistence profiles (including ephemeral vs persistent shapes) the platform will actually accept before you commit to a template name.
- **Browser handoff**: When a person must review, approve, or decide, mint a short-lived `open_link` instead of embedding long-lived credentials in agent code.
- **Identity and scope**: Sign-in sessions, API keys, and layered access to control-plane APIs, sandbox proxies, and per-sandbox grants—least privilege for both operators and automation.
- **Usage under your plan**: Remaining compute, storage quota, which templates you can use, concurrency caps, and max runtime—so autonomous runs stay predictable.
- **MCP in sandbox**: Expose a Model Context Protocol server inside a sandbox through the data-plane proxy (`urls.proxy` + path, API key auth). See [MCP in sandbox](/docs/mcp-sandbox.md).

## Get Started

1. Create an account at [/auth/sign-up](/auth/sign-up).
2. Follow [CLI Guide](/docs/cli-guide.md) to install the CLI and authenticate, then [Sandbox Lifecycle](/docs/sandbox-lifecycle.md) to create and run your first sandbox.
3. Open **Integrate** when you need install and auth for one surface — each guide is self-contained: [CLI Guide](/docs/cli-guide.md), [REST API Guide](/docs/rest-api-guide.md), [Python SDK Guide](/docs/python-sdk-guide.md), [MCP in sandbox](/docs/mcp-sandbox.md). For the hosted control plane, interactive REST documentation (Swagger UI) is at [https://api.treadstone-ai.dev/docs](https://api.treadstone-ai.dev/docs).
4. Use **Core Workflows** for task-focused pages. Where it helps, the same workflow is shown for **CLI**, **REST API**, and **Python SDK** in parallel (on the website you can switch tabs; the raw Markdown file always contains all three).

> For automation: use `sandbox_id`, not `name`. Read `urls.proxy`, `web_url`, and `open_link` from platform output. Do not construct them yourself. Share **`open_link`** for handoffs; **`web_url`** is not a bearer link — it needs a Console session.

## Read Next

- [CLI Guide](/docs/cli-guide.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Usage & Limits](/docs/usage-limits.md)
