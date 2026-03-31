# REST API Guide

Use this when another service needs direct control-plane calls into Treadstone without the CLI or SDK.

## Start With An API Key

Create one in the Console or with the CLI:

```bash
treadstone api-keys create --name service-key --save
```

All programmatic REST integrations should use API keys. Control-plane routes also accept session cookies, but that is for browser-based UIs, not service-to-service calls.

## Create A Sandbox

```bash
curl -X POST https://api.treadstone-ai.dev/v1/sandboxes \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"aio-sandbox-tiny","name":"agent-demo"}'
```

The response comes back immediately with the sandbox record. Save these fields:

- `id` — the machine identifier; used in every follow-up request
- `status` — the initial lifecycle state
- `urls.proxy` — the data-plane entry for proxying requests into this sandbox
- `urls.web` — the browser entry point once a web link is enabled

## Generate A Browser Handoff URL

```bash
curl -X POST https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

From the response:

- `open_link` — the shareable handoff URL to send to a human
- `web_url` — the canonical browser address for this sandbox
- `expires_at` — when this handoff session expires

## Control Plane vs Data Plane

Treadstone has two surfaces with different auth rules:

- **Control plane** (`https://api.treadstone-ai.dev`): auth, templates, sandbox lifecycle, browser handoff, usage. Accepts session cookies or API keys.
- **Data plane** (`/v1/sandboxes/{sandbox_id}/proxy/{path}`): proxies requests directly into a running sandbox. Requires an API key — session cookies are not accepted here.

> For automation: follow operations by `id`, not `name`. Never reconstruct `web_url` or `open_link` from client-side templates.

## Read Next

- [API Reference](/docs/api-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
