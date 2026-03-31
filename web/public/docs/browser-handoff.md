# Browser Handoff

The browser handoff is how an agent passes control to a human. The agent completes the setup work — launching the sandbox, loading state, configuring tools — then generates a short-lived authenticated URL. The human opens that URL in a real browser and sees the live sandbox session, no credentials required on their end.

There are two URL fields you will encounter: `open_link` and `web_url`. They are not interchangeable. `open_link` is what the platform generates for a specific handoff session — it is the URL you send to a human. `web_url` is the canonical browser address for the sandbox, and it requires its own authentication. Always use `open_link` for handoffs.

## Generate A Handoff URL

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

The response contains three fields to keep:

- `open_link` — the shareable URL. This is what you send to the human.
- `web_url` — the canonical browser entry for this sandbox.
- `expires_at` — when this handoff session expires.

If a handoff is already active, `enable` returns the current live link rather than creating a new one.

## Check Handoff Status

```bash
treadstone --json sandboxes web status SANDBOX_ID
```

Use this to confirm whether a handoff is currently active and when it was last used. The status response includes `enabled`, `web_url`, `expires_at`, and `last_used_at`. Note that it does not return `open_link` — to get the shareable URL, call `enable`.

## Revoke And Refresh

```bash
treadstone sandboxes web disable SANDBOX_ID
treadstone --json sandboxes web enable SANDBOX_ID
```

Revoking invalidates the current link immediately. Call `enable` again to issue a fresh one with a new expiry.

> For automation: always call the platform and read `open_link` from the response. Never construct or guess browser URLs from `sandbox_id` or `web_url` templates.

## Read Next

- [API Keys & Auth](/docs/api-keys-auth.md)
- [API Reference](/docs/api-reference.md)
