# API Keys & Auth

Treadstone has two surfaces with different auth rules. The **control plane** handles creating and managing sandboxes, issuing handoff links, and inspecting usage. The **data plane** proxies requests directly into a running sandbox through `/proxy`. Knowing this split determines which credential you need — and where session cookies stop working.

## Sessions vs API Keys

**Saved sessions** are for interactive use — humans running CLI commands or using the Console. After `treadstone auth login`, your session is stored locally and used automatically.

```bash
treadstone auth login
treadstone auth whoami
```

**API keys** are for programmatic and automated use. They are reusable, non-interactive, and explicit about scope. Any process that runs without a human in the loop should use an API key.

## Create An API Key

```bash
treadstone api-keys create --name service-key --save
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

## Read Next

- [CLI Guide](/docs/cli-guide.md)
- [REST API Guide](/docs/rest-api-guide.md)
- [API Reference](/docs/api-reference.md)
