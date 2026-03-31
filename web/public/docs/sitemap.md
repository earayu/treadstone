# Treadstone Documentation Sitemap

This file is generated from `/docs/_manifest.json`.
Read [`/docs/index.md`](/docs/index.md) first if you are new.

## Get Started

- [Overview](/docs/index.md): What Treadstone is and what you can build; introduces control plane vs data plane in plain language, then points to Sandbox endpoints for URLs.
- [Quickstart](/docs/quickstart.md): Install the CLI, sign in, optional API key, and create your first sandbox—bridge to Core Workflows.
- [Sandbox endpoints](/docs/sandbox-endpoints.md): Control plane vs data plane, CLI/SDK/HTTP vs Web and proxy, Web/MCP/Proxy URLs in the Console, and API key use on the data plane.

## Core Workflows

- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md): Create, list, inspect, stop, start, and delete sandboxes. Sandboxes only consume Compute Units while running.
- [Browser Handoff](/docs/browser-handoff.md): Let humans enter the sandbox in a browser: authenticated session or owner-shared JWT link; full workspace view and human-in-the-loop control.
- [API Keys & Auth](/docs/api-keys-auth.md): Sign up via CLI or Console OAuth (Google/GitHub), then session login, API keys, control-plane vs data-plane access, and selected sandbox grants.
- [Usage & Limits](/docs/usage-limits.md): Read plan limits, compute remaining, storage quota, allowed templates, concurrency limits, and billing-period status.

## Integrate

- [CLI Guide](/docs/cli-guide.md): Install the CLI and core behavior: global flags, credential precedence, JSON vs human output, --help, skills, defaults, and local config.
- [REST API Guide](/docs/rest-api-guide.md): REST shape: base URL, /v1 and /health, headers, JSON, errors, OpenAPI, control vs data plane — not duplicate workflows.
- [MCP in sandbox](/docs/mcp-sandbox.md): Expose an MCP server inside a sandbox via the data-plane proxy: urls.proxy + /mcp, API key auth, HTTP/SSE and WebSocket transports, query forwarding, and when to use subdomain browser URLs.
- [Python SDK Guide](/docs/python-sdk-guide.md): Install treadstone-sdk, AuthenticatedClient, module layout, sync vs detailed vs asyncio, errors, regeneration — not duplicate workflows.

## Reference

- [API Reference](/docs/api-reference.md): The user-facing control-plane contract: auth, sandboxes, browser handoff, proxy, usage endpoints, pagination, and error shape.
- [CLI Reference](/docs/cli-reference.md): Root options, command groups, auth precedence, JSON mode, config keys, and the exact hosted CLI surface.
- [Python SDK Reference](/docs/python-sdk-reference.md): Real import paths, generated endpoint modules, request and response models, and sync or async call shapes.
- [Error Reference](/docs/error-reference.md): The stable JSON error envelope, common public error codes, and the recovery step that matches each failure.

## Public Endpoints

- [`/docs/{slug}`](/docs/index): Returns raw Markdown when the client sends `Accept: text/markdown`; otherwise redirects to `/docs?page={slug}`.
- [`/docs/sitemap.md`](/docs/sitemap.md): This complete documentation index.
- [`/llms.txt`](/llms.txt): Short machine-oriented entrypoint.
- [`/openapi.json`](/openapi.json): Generated OpenAPI document for the control plane.
