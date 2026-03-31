# Overview

Treadstone is **agent-native sandbox infrastructure**: a hosted service so you can spin up isolated environments for agents and teams, run tools and code inside them, and **bring a human in with one link** when judgement matters—without building your own control plane, identity, and routing for every project.

The bet is simple: **sandboxes are for automation first.** Humans step in for review, approval, or decisions—not to babysit every create-and-teardown. A raw container is not an agent platform; what matters is stable interfaces around lifecycle, access, and limits so agents can run end-to-end reliably.

## Why it matters

- **One contract, three ways in** — CLI, REST API, and Python SDK share the same resources and shapes, so humans and agents do not diverge.
- **Predictable operations** — Create, inspect, start, stop, and delete sandboxes on demand; templates match what your plan allows.
- **Identity that fits automation** — Sessions and API keys with scoped access so operators and scripts can both work safely.
- **Humans when needed** — Short-lived browser handoff links instead of embedding long-lived credentials in agent code.
- **Room to grow** — Usage, quotas, and plan limits keep autonomous runs bounded.

## What you can build

- **Long-running agent tasks** in isolated runtimes with files, shell, and optional browser.
- **Integrations** that call the same APIs from scripts, services, or the [Python SDK](/docs/python-sdk-guide.md).
- **Human-in-the-loop** flows when something must be seen or approved in a real browser session.

When you are ready to run commands, go to [Quickstart](/docs/quickstart.md), then **Core Workflows** for task-focused guides (sandboxes, auth, browser handoff, limits). **Integrate** holds per-surface install and usage (CLI, REST, SDK, MCP).

## Read next

- [Quickstart](/docs/quickstart.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [CLI Guide](/docs/cli-guide.md)
