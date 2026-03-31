# Browser Handoff

Browser handoff is how a human opens the sandbox in a normal web page: the same runtime the agent uses, viewed and controlled from a browser.

Access is always gated in one of two ways. If the visitor is signed into the Treadstone account in the browser, they can reach the workspace from the Console or a normal login flow. Alternatively, the owner can issue a short-lived `open_link` with a handoff token on `/_treadstone/open`. Anyone who has that URL can enter without a Treadstone login in that tab; possession of the link is the credential. It expires according to `expires_at`; revoke or refresh if it leaks.

So this is not a public directory: you either open `web_url` when you already have an account session, or you use `open_link` when you intend to share entry deliberately.

How `urls.web` relates to the Console Web row and to the control plane vs data plane is summarized in [Sandbox endpoints](/docs/sandbox-endpoints.md).

## How to use the Web URL

1. Read `urls.web` from `GET /v1/sandboxes/{id}` or the Console Endpoints → Web link.
2. Open it in a browser for the workspace UI. It may include `/_treadstone/open?token=…` while a handoff session is active.
3. For a shareable link that works without a Console login in that browser, use `open_link` from `POST /v1/sandboxes/{id}/web-link` (see [Generate a handoff URL](#generate-a-handoff-url)), not a guessed URL.

## What The Human Sees

Opening the handoff shows the full workspace in the browser: the in-sandbox browser, VS Code (including the integrated terminal), the file tree, Jupyter, and anything else running there—the same surfaces the agent can use.

It is also the usual human-in-the-loop entry: someone can watch what the agent is doing and step in to type, click, or fix things when review or takeover is needed.

![Sandbox browser handoff view](/docs/images/sandbox.png)

## Generate A Handoff URL

### CLI

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

```json
{
  "open_link": "https://sb_3kx9m2p.web.treadstone-ai.dev/_treadstone/open?token=swlabc123",
  "web_url": "https://sb_3kx9m2p.web.treadstone-ai.dev/",
  "expires_at": "2026-04-01T12:00:00+00:00"
}
```

The response contains three fields to keep:

- `open_link` — the shareable URL (token in the query string; anyone with the link can enter).
- `web_url` — the canonical browser host; opening it requires a **logged-in** Console session, not suitable as a standalone share link.
- `expires_at` — when this handoff session expires.

If a handoff is already active, `enable` returns the current live link rather than creating a new one.

### REST API

```bash
curl -sS -X POST "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

Read `open_link`, `web_url`, and `expires_at` from the JSON body.

### Python SDK

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes.sandboxes_create_sandbox_web_link import (
    sandboxes_create_sandbox_web_link,
)

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",
)

session = sandboxes_create_sandbox_web_link.sync("SANDBOX_ID", client=client)
print(session.open_link)
print(session.expires_at)
```

## Check Handoff Status

### CLI

```bash
treadstone --json sandboxes web status SANDBOX_ID
```

```json
{
  "web_url": "https://sb_3kx9m2p.web.treadstone-ai.dev/",
  "enabled": true,
  "expires_at": "2026-04-01T12:00:00+00:00",
  "last_used_at": "2026-03-31T11:30:00+00:00"
}
```

Use this to confirm whether a handoff is currently active and when it was last used. The status response includes `enabled`, `web_url`, `expires_at`, and `last_used_at`. Note that it does not return `open_link` — to get the shareable URL, call `enable`.

### REST API

```bash
curl -sS "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python SDK

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes.sandboxes_get_sandbox_web_link import (
    sandboxes_get_sandbox_web_link,
)

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",
)

status = sandboxes_get_sandbox_web_link.sync("SANDBOX_ID", client=client)
print(status.enabled, status.expires_at, status.last_used_at)
```

## Revoke And Refresh

### CLI

```bash
treadstone --json sandboxes web disable SANDBOX_ID
```

```json
{
  "detail": "Sandbox web access disabled.",
  "sandbox_id": "sb_3kx9m2p"
}
```

```bash
treadstone --json sandboxes web enable SANDBOX_ID
```

```json
{
  "open_link": "https://sb_3kx9m2p.web.treadstone-ai.dev/_treadstone/open?token=swlnew456",
  "web_url": "https://sb_3kx9m2p.web.treadstone-ai.dev/",
  "expires_at": "2026-04-02T12:00:00+00:00"
}
```

Revoking invalidates the current link immediately. Call `enable` again to issue a fresh one with a new expiry.

### REST API

```bash
curl -sS -X DELETE "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"

curl -sS -X POST "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID/web-link" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

### Python SDK

```python
from treadstone_sdk import AuthenticatedClient
from treadstone_sdk.api.sandboxes.sandboxes_create_sandbox_web_link import (
    sandboxes_create_sandbox_web_link,
)
from treadstone_sdk.api.sandboxes.sandboxes_delete_sandbox_web_link import (
    sandboxes_delete_sandbox_web_link,
)

client = AuthenticatedClient(
    base_url="https://api.treadstone-ai.dev",
    token="sk-...",
)

sandboxes_delete_sandbox_web_link.sync("SANDBOX_ID", client=client)
session = sandboxes_create_sandbox_web_link.sync("SANDBOX_ID", client=client)
print(session.open_link)
```

> For automation: always call the platform and read `open_link` from the response. Never construct or guess browser URLs from `sandbox_id` or `web_url` templates.

## `open_link` vs `web_url` (API field reference)

Use this section when you are parsing JSON or automating. The names `open_link` and `web_url` are **public API fields**—they are not internal-only identifiers. In prose above, “shareable handoff URL” corresponds to `open_link`; “canonical workspace browser URL” corresponds to `web_url`.

You will see two URL fields in API responses. They are not interchangeable.

A typical place they appear together is the JSON from `POST /v1/sandboxes/{sandbox_id}/web-link` (or `treadstone sandboxes web enable`). Pull both out with `jq` so you can compare shapes side by side:

```bash
export SANDBOX_ID="sb_your_sandbox_id"

# Same response shape from the CLI:
# treadstone --json sandboxes web enable "$SANDBOX_ID" | jq '{open_link, web_url}'

curl -sS -X POST "https://api.treadstone-ai.dev/v1/sandboxes/${SANDBOX_ID}/web-link" \
  -H "Authorization: Bearer ${TREADSTONE_API_KEY}" | jq '{open_link, web_url}'
```

Example (truncated paths; real tokens are longer):

```json
{
  "open_link": "https://sb_3kx9m2p.web.treadstone-ai.dev/_treadstone/open?token=swl…",
  "web_url": "https://sb_3kx9m2p.web.treadstone-ai.dev/"
}
```

`open_link` is the shareable handoff URL. It includes a token on `/_treadstone/open?token=…` that the edge accepts for browser access. Anyone who receives the link can use it to enter the sandbox without signing into Treadstone in that tab. Use it when you send someone a “click and you are in” link, or when automation needs a one-shot entry URL.

`web_url` is the canonical browser hostname for the sandbox (usually the sandbox root). You cannot treat it like `open_link`. Opening `web_url` in a fresh browser session does not grant access by itself: the visitor goes through account sign-in so the platform can establish a logged-in session. Share `open_link` for handoffs; use `web_url` when the user is already signed in.

Always obtain `open_link` from the platform response. Do not guess URLs from `sandbox_id` alone.

## Read Next

- [API Keys & Auth](/docs/api-keys-auth.md)
- [API Reference](/docs/api-reference.md)
