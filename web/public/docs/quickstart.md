# Quickstart

Install the CLI, point it at the hosted cloud, and you are one login away from a running sandbox with a shareable browser handoff URL.

```bash
pip install treadstone-cli
export TREADSTONE_BASE_URL="https://api.treadstone-ai.dev"
```

## Sign In

```bash
treadstone auth login
```

This opens a browser-based login flow. For fully non-interactive environments, pass credentials directly: `treadstone auth login --email you@example.com --password 'StrongPass123!'`. After login, a session is saved locally — no need to pass credentials on every command.

## Pick A Template And Create A Sandbox

```bash
treadstone --json templates list
treadstone --json sandboxes create --template aio-sandbox-tiny --name demo
```

Templates are the runtime shapes your plan allows — `templates list` shows what your account can actually use. The `create` command returns `202 Accepted` immediately with the sandbox record. Save `id` and `urls.proxy` from the response; every follow-up operation uses `id`.

## Hand The Browser To A Human

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

This returns `open_link`, `web_url`, and `expires_at`. Share `open_link` — that is the human-facing handoff URL. Do not use `web_url` directly; it requires its own authentication.

## Switch To Non-Interactive Auth

If a human will not complete the browser login flow, create a reusable API key and continue without the session:

```bash
treadstone api-keys create --name service-key --save
```

Then choose your integration path:

- [CLI Guide](/docs/cli-guide.md) — scripted, automation-friendly operator commands
- [REST API Guide](/docs/rest-api-guide.md) — direct control-plane HTTP calls from any language
- [Python SDK Guide](/docs/python-sdk-guide.md) — generated Python models and typed clients

## Read Next

- [Create a Sandbox](/docs/create-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
