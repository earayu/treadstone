# Browser Handoff

## What this page is for

Explain the browser hand-off model without ambiguity.

## Use this when

- An agent needs a human to inspect or approve something.
- You need to create, inspect, or revoke browser hand-off access.
- You need to know the difference between `web_url` and `open_link`.

## Shortest path

```bash
treadstone --json sandboxes web enable SANDBOX_ID
treadstone --json sandboxes web status SANDBOX_ID
treadstone sandboxes web disable SANDBOX_ID
```

## Hard rules

- The route is `/v1/sandboxes/{sandbox_id}/web-link`.
- `web_url` is the canonical browser origin.
- `open_link` is the shareable URL you hand to a human.
- Never derive browser URLs from the sandbox name.

## Create or Refresh a Browser Link

CLI:

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

API:

```text
POST /v1/sandboxes/{sandbox_id}/web-link
```

The response includes:

- `web_url`
- `open_link`
- `expires_at`

## Inspect Current Browser-Link State

CLI:

```bash
treadstone --json sandboxes web status SANDBOX_ID
```

API:

```text
GET /v1/sandboxes/{sandbox_id}/web-link
```

The status response includes:

- `web_url`
- `enabled`
- `expires_at`
- `last_used_at`

## Revoke Browser Access

CLI:

```bash
treadstone sandboxes web disable SANDBOX_ID
```

API:

```text
DELETE /v1/sandboxes/{sandbox_id}/web-link
```

## How It Works

- If sandbox subdomain routing is configured, Treadstone knows the canonical browser origin.
- The platform stores a server-side web-link record tied to the sandbox.
- `open_link` carries the bootstrap token that hands the session to the browser.

## When to Use Browser Handoff

- A human has to review rendered output.
- OAuth or browser-only actions must happen in a real page.
- The agent wants a human decision without exposing the raw sandbox internals.

## For Agents

- Use `open_link` for hand-off.
- Use `web_url` if you need the canonical origin after the hand-off already exists.
- If `enabled` is false, create a new web link instead of guessing whether an old one still works.
