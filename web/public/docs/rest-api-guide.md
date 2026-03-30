# REST API Guide

Use this when another service needs direct control-plane calls into hosted Treadstone.

## Start With An API Key

Create one in the Console or with the CLI:

```bash
treadstone api-keys create --name service-key --save
```

Programmatic REST integrations should usually use API keys, even though control-plane routes also accept session cookies.

## Create A Sandbox

```bash
curl -X POST https://api.treadstone-ai.dev/v1/sandboxes \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"aio-sandbox-tiny","name":"agent-demo"}'
```

Save:

- `id`
- `status`
- `urls.proxy`
- `urls.web`

## Hand The Browser To A Human

```bash
curl -X POST https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

Read:

- `web_url`
- `open_link`
- `expires_at`

## Know The Surface Split

- Control plane: auth, templates, sandboxes, browser handoff, usage
- Data plane: `/v1/sandboxes/{sandbox_id}/proxy/{path}`

The data plane requires an API key. Cookie sessions do not work there.

> For automation: follow the workflow with `id`, not `name`. Never reconstruct `web_url` or `open_link` on the client side.

## Read Next

- [API Reference](/docs/api-reference.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
