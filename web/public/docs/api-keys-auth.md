# API Keys & Auth

Treadstone has two surfaces with different auth rules. The control plane handles creating and managing sandboxes, issuing handoff links, and inspecting usage. The data plane proxies requests into a running sandbox through `/proxy`. Knowing this split tells you which credential to use and where session cookies stop working.

## Registration

You need an account before `treadstone auth login`, the Console, or creating API keys.

### CLI

```bash
# Create an account from the terminal:
treadstone auth register


# The CLI prompts for email and password. For scripts or CI, pass them explicitly:
treadstone auth register --email you@example.com --password 'YourPass123!'
```

### Web Console (OAuth)

Open the Treadstone web app and sign up with **Google** or **GitHub** OAuth. After OAuth completes, you can use the Console with your session or run `treadstone auth login` from the CLI (same account).

## Sessions vs API Keys

### Saved sessions

Saved sessions are for interactive use: humans running CLI commands or using the Console. After `treadstone auth login`, your session is stored locally and used automatically.

```bash
treadstone auth login
treadstone --json auth whoami
```

```json
{
  "id": "usr-abc123def456",
  "email": "you@example.com",
  "role": "user",
  "is_active": true,
  "username": null,
  "is_verified": true,
  "has_local_password": true
}
```

### API keys

API keys are for programmatic and automated use. They are reusable, non-interactive, and explicit about scope. Any process that runs without a human in the loop should use an API key.

## In the Console

On the Keys page, each row shows the key name, a masked preview, scope badges (control plane and/or data plane), created time, expiry, and whether the key is enabled. That matches the `scope` object you get from the API or CLI when you create or list keys.

![API Keys table: name, preview, scope, expiry, and status](/docs/images/api-keys-console-table.png)

## Create An API Key

```bash
treadstone api-keys create --name service-key --save
```

```json
{
  "id": "key-abc123def456",
  "name": "service-key",
  "is_enabled": true,
  "key": "sk-0123456789abcdef0123456789abcdef01234567",
  "created_at": "2026-03-31T10:00:00+00:00",
  "updated_at": "2026-03-31T10:00:00+00:00",
  "expires_at": null,
  "scope": {
    "control_plane": true,
    "data_plane": { "mode": "all", "sandbox_ids": [] }
  }
}
```

The full key value is shown exactly once. Save it immediately — it cannot be retrieved again.

## Scope A Key To The Data Plane

By default, a new key can reach both surfaces. Narrow the scope when a key should only proxy requests into specific sandboxes:

```bash
treadstone api-keys create \
  --name selected-proxy \
  --no-control-plane \
  --data-plane selected \
  --sandbox-id SANDBOX_ID
```

```json
{
  "id": "key-def456ghi789",
  "name": "selected-proxy",
  "is_enabled": true,
  "key": "sk-fedcba9876543210fedcba9876543210fedcba98",
  "created_at": "2026-03-31T10:00:00+00:00",
  "updated_at": "2026-03-31T10:00:00+00:00",
  "expires_at": null,
  "scope": {
    "control_plane": false,
    "data_plane": { "mode": "selected", "sandbox_ids": ["sb_3kx9m2p"] }
  }
}
```

### The scope model

The scope model has three fields:

- `control_plane`: `true` or `false` — whether the key can reach control-plane routes
- `data_plane.mode`: `none`, `all`, or `selected` — the data-plane access level
- `data_plane.sandbox_ids`: an explicit allowlist, only valid when `mode=selected`

## Auth Rules That Matter

- Control-plane routes accept either a saved session or an API key.
- Data-plane `/proxy` routes require an API key. Session cookies do not work there.
- In the CLI, an API key takes precedence over a saved session when both are present.
- Create the smallest key that still completes the job. Long-lived "all access" keys should be rare.

> For automation: use an API key with the minimum required scope. Prefer `selected` data-plane mode when the key only needs to reach one sandbox.

## For Agents

- Register with `POST /v1/auth/register` (body: `email`, `password`) or use `treadstone auth register`; Console users may use Google/GitHub OAuth in the browser instead.
- After registration, interactive flows use `treadstone auth login`; automation uses API keys with minimal scope.

## Read Next

- [Inside your sandbox](/docs/inside-sandbox.md)
- [CLI Guide](/docs/cli-guide.md)
- [REST API Guide](/docs/rest-api-guide.md)
- [API Reference](/docs/api-reference.md)
