# Browser Handoff

**Browser handoff** is how a **human enters the sandbox through a normal web page** — the same runtime the agent is using, but viewed and controlled from a browser.

Access is **always gated**:

- **Account session** — the sandbox owner (or anyone signed into that Treadstone account in the browser) can open the workspace after navigating from the Console or a normal login flow.
- **Shared link** — the owner can **issue a short-lived URL** (`open_link`) that includes a **handoff token** on `/_treadstone/open`. **Anyone who has the link** can open the workspace in the browser without signing into Treadstone — possession of the URL is the credential. It expires on the schedule you see as `expires_at`; revoke or refresh if it leaks.

So this is not a public directory: either you use `web_url` with an **account session** (Console login) in the browser, or you use `open_link` as a deliberate, shareable entry.

## What The Human Sees

Opening the handoff gives a **full browser view into the container**: the in-sandbox browser, VS Code (including the integrated terminal), the file tree, Jupyter, and anything else running there — the same surfaces the agent can use.

In practice it is also the **human-in-the-loop entry**: someone can **watch** what the agent is doing inside the sandbox and **step in** to type, click, or fix things when review or takeover is needed.

## `open_link` vs `web_url`

You will see two URL fields in API responses. They are **not** interchangeable:

- **`open_link`** — the **shareable** handoff URL. It includes a **token** on `/_treadstone/open?token=…` that the edge accepts to issue browser access. **Anyone who receives the link** can use it to enter the sandbox — no Treadstone login is required in that browser tab. **Use this** when you send someone a “click and you are in” link, or when automation needs a one-shot entry URL.
- **`web_url`** — the **canonical** browser hostname for the sandbox (usually the sandbox root). **You cannot treat it like `open_link`.** Opening `web_url` in a fresh browser session does **not** grant access by itself: the visitor is sent through **account sign-in** (Console session) so the platform can establish a normal, logged-in browser session. Share `open_link` for handoffs; bookmark or use `web_url` only in contexts where the user is already signed in.

Always obtain `open_link` from the platform response — never guess URLs from `sandbox_id` alone.

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

## Read Next

- [API Keys & Auth](/docs/api-keys-auth.md)
- [API Reference](/docs/api-reference.md)
