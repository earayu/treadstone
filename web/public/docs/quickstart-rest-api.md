# Quickstart for REST API

## What this page is for

Give you the shortest working HTTP path through the control plane.

## Use this when

- You need explicit requests and responses.
- You are integrating from a language without the SDK.
- You want the route truth without reading the full reference.

## Shortest path

```bash
export BASE_URL="https://api.treadstone-ai.dev"
export TREADSTONE_API_KEY="sk-..."

curl -s "$BASE_URL/health"
curl -s "$BASE_URL/v1/sandbox-templates" -H "Authorization: Bearer $TREADSTONE_API_KEY"
curl -s -X POST "$BASE_URL/v1/sandboxes" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"template":"aio-sandbox-tiny","name":"rest-demo"}'
curl -s -X POST "$BASE_URL/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

## Hard rules

- Use `Authorization: Bearer sk-...` for API key auth.
- Control-plane routes accept session cookie or API key. This page uses API keys.
- Sandbox creation returns `202 Accepted`.
- Browser hand-off uses `/v1/sandboxes/{sandbox_id}/web-link`, not `/web/enable`.

## Step 1: Health

```bash
curl -s "$BASE_URL/health"
```

Expected body:

```json
{"status":"ok"}
```

## Step 2: List templates

```bash
curl -s "$BASE_URL/v1/sandbox-templates" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

## Step 3: Create a sandbox

```bash
curl -s -X POST "$BASE_URL/v1/sandboxes" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "aio-sandbox-tiny",
    "name": "rest-demo",
    "persist": false
  }'
```

Read:

- `id`
- `status`
- `urls.proxy`
- `urls.web`

## Step 4: Issue a browser hand-off URL

```bash
curl -s -X POST "$BASE_URL/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

Read:

- `web_url`
- `open_link`
- `expires_at`

## Step 5: Use the data plane when needed

```bash
curl -i "$BASE_URL/v1/sandboxes/SANDBOX_ID/proxy/" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

That path is the sandbox proxy. It is the data plane. Read [`guide-data-plane-access.md`](/docs/guide-data-plane-access.md) before sending real traffic.

## For Agents

- The create response is not the same thing as a ready proxy target. Inspect current state before assuming readiness.
- Use [`api-reference.md`](/docs/api-reference.md) when you need the full route map.
