# Overview

**Treadstone is a hosted sandbox platform built for AI agents and the teams behind them.** Spin up isolated environments on demand, run code and tools inside them, drive a real browser when your workflow needs one, and—when judgement matters—**hand the same session to a human with a normal link**. No DIY control plane, no wiring a new ingress stack for every project.

**Why it exists:** agents need **repeatable** infrastructure—stable ways to create and tear down environments, authenticate automation, and **not** paste secrets into prompts. Humans show up for **review, approval, or takeover**, not to babysit every sandbox lifecycle.

## What you can do

- **Ship agent workflows** — Create sandboxes from templates, run long tasks in isolation, and integrate from scripts, services, or backends using the same platform surface.
- **Same tools, many surfaces** — Drive the platform from the [CLI](/docs/cli-guide.md), [REST](/docs/rest-api-guide.md), or [Python SDK](/docs/python-sdk-guide.md)—pick what fits your stack.
- **Bring a person in** — Short-lived **browser handoff** when someone needs to see or steer what the agent is doing ([Browser Handoff](/docs/browser-handoff.md)).
- **Stay inside your plan** — Templates, concurrency, and usage are bounded by your account; see [Usage & Limits](/docs/usage-limits.md) for the numbers.

## Ideas to keep in mind (high level)

Almost everything in the product falls into two ideas that are easy to keep straight:

- **Managing the platform** — accounts, sandboxes, keys, templates, usage: you are talking to Treadstone to drive your project. In the docs we call that the **control plane**.
- **Reaching what runs inside a sandbox** — the browser workspace, HTTP into the workload, MCP for AI tools: traffic is going into the box where the agent’s work runs. We call that the **data plane**.

You only need those two names and what they stand for at first. When you want concrete URLs and field names (**Web**, **MCP**, **Proxy**, and **`urls.*`** in API responses), read [Sandbox endpoints](/docs/sandbox-endpoints.md). To **call HTTP into a running sandbox** (data plane), follow [Using the data plane](/docs/data-plane.md). For REST shape and auth, continue with [REST API Guide](/docs/rest-api-guide.md) and [API Keys & Auth](/docs/api-keys-auth.md).

## See it in action (media)

We are adding screenshots, GIFs, and short videos here—examples like **an agent creating a sandbox and then driving the workspace inside**. Until those ship, start with [Quickstart](/docs/quickstart.md).

## Read next

- [Quickstart](/docs/quickstart.md)
- [Sandbox endpoints](/docs/sandbox-endpoints.md)
- [Using the data plane](/docs/data-plane.md)
- [Usage & Limits](/docs/usage-limits.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
- [CLI Guide](/docs/cli-guide.md)
