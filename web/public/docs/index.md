# Overview

Treadstone is the hosted control plane for agent sandboxes. You create a sandbox, route work into it, and hand the browser to a human only when the workflow actually needs one.

A raw container is not an agent platform. The runtime matters, but so does everything around it: identity, lifecycle, scope, browser review, and plan limits. If a human still has to babysit auth, sandbox state, routing, and browser access, the agent is not really autonomous. Treadstone closes that gap.

## Choose Your Entry Point

Pick based on your workflow:

- **Console** — browser UI at the hosted URL. Best for getting started by hand, checking plan limits, and managing a hosted account without writing code.
- **CLI** — `pip install treadstone-cli`. Best for the shortest interactive or scripted path. Outputs machine-safe JSON when you pass `--json`.
- **REST API** — calls against `https://api.treadstone-ai.dev`. Best when another service needs direct control-plane access.
- **Python SDK** — `pip install treadstone-sdk`. Best when you already live in Python and want generated request and response models.

## What The Platform Gives You

- **Sandbox lifecycle**: create, inspect, start, stop, and delete environments on demand.
- **Template catalog**: discover the runtime shapes the platform will actually accept for your plan.
- **Browser handoff**: issue a short-lived `open_link` when a human needs to step in and review or decide.
- **Auth and scope control**: sessions, API keys, control-plane access, data-plane access, and selected sandbox grants.
- **Usage and limits**: remaining compute, storage quota, template access, concurrency, and max runtime duration.

## Get Started

1. Create an account at [/auth/sign-up](/auth/sign-up).
2. Read [Quickstart](/docs/quickstart.md) for the shortest path to a running sandbox.
3. Then continue with [CLI Guide](/docs/cli-guide.md), [REST API Guide](/docs/rest-api-guide.md), or [Python SDK Guide](/docs/python-sdk-guide.md).

> For automation: use `sandbox_id`, not `name`. Read `urls.proxy`, `web_url`, and `open_link` from platform output. Do not construct them yourself.

## Read Next

- [Quickstart](/docs/quickstart.md)
- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Usage & Limits](/docs/usage-limits.md)
