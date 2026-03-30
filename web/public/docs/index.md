# Overview

Treadstone is the hosted control plane for agent sandboxes. You create a sandbox, route work into it, and hand the browser to a human only when the workflow actually needs a human.

It is for teams building agents that need a real runtime: files, tools, long-running state, and a browser that can be shared without improvising auth, URLs, or lifecycle rules.

## Choose Your Interface

### Console

Best when you are getting started by hand, checking plan limits, or managing a hosted account.

### CLI

Best when you want the shortest path, repeatable commands, and machine-safe JSON output.

### REST API

Best when another service needs direct control-plane access.

### Python SDK

Best when you already live in Python and want generated request and response models.

## Get Started

1. Create an account at [/auth/sign-up](/auth/sign-up).
2. Read [Quickstart](/docs/quickstart.md).
3. Then continue with [CLI Guide](/docs/cli-guide.md), [REST API Guide](/docs/rest-api-guide.md), or [Python SDK Guide](/docs/python-sdk-guide.md).

## What You Actually Get

- Sandbox lifecycle: create, inspect, start, stop, and delete.
- Template discovery: read the runtime shapes the platform will actually accept.
- Browser handoff: issue an `open_link` when a human needs to review or decide.
- Auth and scope control: sessions, API keys, control-plane access, data-plane access, and selected sandbox grants.
- Usage and limits: remaining compute, storage quota, template access, concurrency, and max runtime duration.

## Why This Exists

Treadstone is not just a runtime rental API. The runtime matters, but the control plane around the runtime matters just as much: identity, lifecycle, scope, browser review, and plan limits.

If a human still has to babysit auth, sandbox state, routing, and browser access, the agent is not really autonomous. Treadstone closes that gap.

> For automation: use `sandbox_id`, not `name`. Read `urls.proxy`, `web_url`, and `open_link` from platform output. Do not construct them yourself.

## Read Next

- [Quickstart](/docs/quickstart.md)
- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Usage & Limits](/docs/usage-limits.md)
