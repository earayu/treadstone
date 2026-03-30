# Core Concepts

## What this page is for

Define the nouns, boundaries, and invariants that all other docs assume.

## Use this when

- A command or route only makes sense if you understand the platform split.
- You need to know which identifier or credential belongs where.
- You are deciding whether a task belongs to the control plane or the data plane.

## Shortest path

1. Learn `sandbox_id`, `urls.proxy`, `web_url`, and `open_link`.
2. Learn the auth split between control plane and data plane.
3. Learn the difference between ephemeral and persistent sandboxes.

## Hard rules

- `sandbox_id` is the machine identifier. `name` is a human label.
- `urls.proxy` belongs to the data plane. `/v1/sandboxes/*` belongs to the control plane.
- `web_url` is the canonical browser origin. `open_link` is the shareable entry URL.
- Pagination is `limit` plus `offset`, not cursor-based.

## Control Plane

The control plane is the public API surface that governs identity, lifecycle, usage, and administration.

Examples:

- `/v1/auth/*`
- `/v1/sandboxes`
- `/v1/sandboxes/{sandbox_id}/web-link`
- `/v1/usage/*`
- `/v1/admin/*`

This is where you create a sandbox, inspect its state, and decide who can access it.

## Data Plane

The data plane is the sandbox proxy path:

```text
/v1/sandboxes/{sandbox_id}/proxy/{path}
```

This is not where you create sandboxes. This is where you route requests into a sandbox that already exists and is ready.

## Sandbox

A sandbox is an isolated runtime owned by one user. It has:

- an `id`
- a human-readable `name`
- a `template`
- a lifecycle state such as `creating`, `ready`, or `stopped`
- `urls.proxy`
- optional `urls.web`

## Template

A template defines the runtime image and requested resources. List templates through the platform. Do not hardcode names you have not checked.

CLI:

```bash
treadstone templates list
```

API:

```text
GET /v1/sandbox-templates
```

## API Key

An API key has two separate dimensions:

- `control_plane`
- `data_plane`

Data plane scope can be:

- `none`
- `all`
- `selected`

If the mode is `selected`, the key only works for the listed sandbox IDs.

## Browser Handoff

Treadstone separates the stable browser origin from the hand-off token:

- `web_url`: the canonical sandbox browser URL
- `open_link`: the shareable link that carries the bootstrap token

You do not build either one from the sandbox name.

## Plans, Usage, and Grants

User plans carry the baseline limits:

- monthly compute
- storage capacity
- max concurrent running sandboxes
- max sandbox duration
- allowed templates
- grace period

Grants add temporary or supplemental capacity on top.

## Ephemeral vs Persistent

`persist=false` and `persist=true` do not just change a storage flag. They change provisioning strategy:

- `persist=false`: claim path, warm-pool friendly
- `persist=true`: direct sandbox path with volume claims

Use persistent sandboxes when the workspace must survive restart and stop events.

## For Agents

- Never substitute `name` where a route asks for `sandbox_id`.
- Never assume control-plane auth rules apply to the proxy path.
- Never assume `persist=true` behaves like a trivial addon to an ephemeral sandbox.
- When in doubt, inspect the current object returned by the control plane and continue from that response.
