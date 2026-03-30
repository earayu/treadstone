# Quickstart

This is the fastest hosted path from a new account to a running sandbox and a shareable browser handoff URL.

## Fastest Path

```bash
pip install treadstone-cli
export TREADSTONE_BASE_URL="https://api.treadstone-ai.dev"

treadstone auth login
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
treadstone --json sandboxes web enable SANDBOX_ID
```

## What To Save

- `id` from `sandboxes create`
- `urls.proxy` from `sandboxes create`
- `web_url`, `open_link`, and `expires_at` from `sandboxes web enable`

## What To Expect

- `auth login` opens a browser flow unless you pass `--email` and `--password`.
- `templates list` returns the template names your account can actually use.
- `sandboxes create` returns `202 Accepted` and the sandbox record immediately.
- `sandboxes web enable` returns the human-facing handoff URL. Open `open_link`, not `web_url`.

> For automation: if a human will not complete the browser login flow, create an API key after login and continue with [CLI Guide](/docs/cli-guide.md) or [REST API Guide](/docs/rest-api-guide.md).

## Choose Your Next Surface

- [CLI Guide](/docs/cli-guide.md) if you want the shortest operator and automation path.
- [REST API Guide](/docs/rest-api-guide.md) if another service will call Treadstone directly.
- [Python SDK Guide](/docs/python-sdk-guide.md) if you want generated Python models and client methods.

## Read Next

- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
