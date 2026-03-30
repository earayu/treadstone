# Browser Handoff

Use this when an agent or service has done the setup and a human needs to open the sandbox in a real browser.

## Create Or Refresh A Handoff URL

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

Read these fields from the response:

- `web_url`
- `open_link`
- `expires_at`

Open `open_link` in the browser. That is the human handoff URL.

## Check Status

```bash
treadstone --json sandboxes web status SANDBOX_ID
```

Read these fields:

- `enabled`
- `web_url`
- `expires_at`
- `last_used_at`

`status` tells you whether a handoff is active. It does not return `open_link`.

## Revoke The Current Link

```bash
treadstone sandboxes web disable SANDBOX_ID
```

If you need a fresh handoff URL, disable the current link and enable it again.

## Rules That Matter

- `open_link` is the shareable handoff URL.
- `web_url` is the canonical browser surface for that sandbox.
- An active `enable` call returns the current live link instead of creating a new one.
- Do not construct sandbox browser URLs from names or string templates.

> For automation: call the platform and read `open_link` from output. Never guess it from `sandbox_id` or `web_url`.

## Read Next

- [API Keys & Auth](/docs/api-keys-auth.md)
- [API Reference](/docs/api-reference.md)
