# API Keys & Auth

Control plane and data plane do not accept the same credentials. This page is the shortest version of that boundary.

## Human Login

Use a saved session when you are operating Treadstone directly:

```bash
treadstone auth login
treadstone auth whoami
```

A saved session works for control-plane actions such as auth, templates, sandboxes, browser handoff, and usage.

## API Keys

Use an API key when another process needs reusable, non-interactive access:

```bash
treadstone api-keys create --name service-key --save
```

The full key is shown once. Save it immediately.

## Scope A Data-Plane Key

```bash
treadstone api-keys create \
  --name selected-proxy \
  --no-control-plane \
  --data-plane selected \
  --sandbox-id SANDBOX_ID
```

Use this when a key should only reach one or a small set of sandboxes through `/proxy`.

## Scope Model

- `control_plane`: `true` or `false`
- `data_plane.mode`: `none`, `all`, or `selected`
- `data_plane.sandbox_ids`: only valid when `mode=selected`

## Rules That Matter

- Control-plane routes accept either a saved session or an API key.
- Data-plane `/proxy` routes require an API key. Cookie sessions do not work there.
- In the CLI, API keys take precedence over a saved session.
- Selected data-plane grants are explicit allowlists, not patterns.

> For automation: create the smallest key that still completes the job. Long-lived "all access" keys should be rare.

## Read Next

- [CLI Guide](/docs/cli-guide.md)
- [REST API Guide](/docs/rest-api-guide.md)
- [API Reference](/docs/api-reference.md)
