# Inside your sandbox

## What this page is for

This is the **practical path** for calling HTTP (or WebSocket) **into a running sandbox** — the same traffic we call the **data plane** in architecture docs ([Sandbox endpoints](/docs/sandbox-endpoints.md)). Here we use plain language: get **`urls.proxy`**, use an API key that can reach this sandbox, and send `curl` or client requests — without guessing URLs.

It does **not** replace [Sandbox Lifecycle](/docs/sandbox-lifecycle.md) (create/start/stop/delete) or [API Keys & Auth](/docs/api-keys-auth.md) (sign-up and scope). Read those first if you are new.

## Prerequisites

1. A **running** sandbox (or one that is ready for traffic — see `status` on [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)).
2. An **API key** with access to this sandbox on the proxy (`data_plane.mode` is `all` or `selected` with this `sandbox_id` in the allowlist). See [API Keys & Auth](/docs/api-keys-auth.md).
3. The **proxy base URL** from the platform — never guess hostnames or paths.

## Get the URLs (control plane, one call)

```bash
export TREADSTONE_API_KEY="sk_..."
treadstone --json sandboxes get SANDBOX_ID
# or: curl -sS "https://api.treadstone-ai.dev/v1/sandboxes/SANDBOX_ID" \
#       -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

Example shape (fields vary; `urls` is what you need here):

```json
{
  "id": "sb_docexample01",
  "name": "demo",
  "status": "running",
  "urls": {
    "proxy": "https://api.treadstone-ai.dev/v1/sandboxes/sb_docexample01/proxy",
    "mcp": "https://api.treadstone-ai.dev/v1/sandboxes/sb_docexample01/proxy/mcp",
    "web": "https://sandbox-sb_docexample01.treadstone-ai.dev/_treadstone/open?token=swl…"
  }
}
```

From that JSON, read **`urls.proxy`** (HTTP prefix into the sandbox) and, if you use MCP, **`urls.mcp`**. Those strings are authoritative; copy them from the response or from the Console Endpoints row ([Sandbox endpoints](/docs/sandbox-endpoints.md)).

## Call HTTP into the workload

Append the path your app serves **after** the `/proxy` segment. The first path segment after `/proxy/` is what the workload receives (see [API Reference](/docs/api-reference.md) for proxy behaviour).

```bash
export TREADSTONE_API_KEY="sk_..."
export PROXY_BASE="https://api.treadstone-ai.dev/v1/sandboxes/sb_xxx/proxy"

curl -sS "$PROXY_BASE/health" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY"
```

## Hands-on examples

These are **multi-step** flows against the same **`$PROXY_BASE`** and **`Authorization: Bearer`**. Routes are the real sandbox runtime paths under `/v1/shell/…`, `/v1/file/…`, `/v1/browser/…` (see [API Reference](/docs/api-reference.md)). Replace placeholders with your sandbox’s **`urls.proxy`** and a key that can reach this sandbox.

### 1) “Trip souvenir”: download a photo, list it, pull it to your laptop

**Goal:** Inside the sandbox, save an image with `curl`, confirm it exists, then copy the file **out** to your machine with the file API (same idea as logs, build artifacts, or checkpoints).

**Step 1 — Create a folder and download an image (shell)**

```bash
curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"mkdir -p /tmp/treadstone-demo && curl -fsSL https://picsum.photos/400/300 -o /tmp/treadstone-demo/souvenir.jpg && ls -la /tmp/treadstone-demo","exec_dir":"/tmp"}'
```

**Step 2 — List the directory (file)**

```bash
curl -sS -X POST "$PROXY_BASE/v1/file/list" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":"/tmp/treadstone-demo"}'
```

**Step 3 — Download the file to your current directory**

```bash
curl -fsS -G "$PROXY_BASE/v1/file/download" \
  --data-urlencode "path=/tmp/treadstone-demo/souvenir.jpg" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -o ./souvenir.jpg
```

Use an **absolute** `path` query parameter; `--data-urlencode` avoids mistakes with `/` characters.

### 2) Screenshot the desktop

**Goal:** Capture what is on the **sandbox display** (for example after you opened the workspace in a browser via `urls.web`, or after other desktop activity).

```bash
curl -fsS "$PROXY_BASE/v1/browser/screenshot" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -o ./desktop.png
```

The body is a PNG (`image/png`). Response headers such as `x-image-width` / `x-image-height` describe the capture.

### 3) Open a URL in the desktop browser, wait, then screenshot

The browser HTTP API exposes **mouse/keyboard** actions, not a dedicated “go to URL” call. On a typical Linux desktop image you can **launch** the system browser from the shell, wait for the page to load, then **screenshot**.

```bash
curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"xdg-open https://example.com 2>/dev/null || sensible-browser https://example.com 2>/dev/null || echo \"no desktop browser helper in PATH\"","exec_dir":"/tmp"}'

curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"sleep 3","exec_dir":"/tmp"}'

curl -fsS "$PROXY_BASE/v1/browser/screenshot" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -o ./after-open-url.png
```

Whether `xdg-open` / `sensible-browser` exists depends on your **template image**. If they are missing, use **example 1** (`curl` inside the sandbox) to fetch assets without a GUI.

### 4) “Keyboard macro”: type into the focused window, wait, screenshot

**Goal:** After focus is in the right place (for example you clicked into a terminal via [Browser Handoff](/docs/browser-handoff.md) or a `CLICK` action), send text and capture the result.

```bash
curl -sS -X POST "$PROXY_BASE/v1/browser/actions" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"TYPING","text":"echo hello from Treadstone\n"}'

curl -sS -X POST "$PROXY_BASE/v1/browser/actions" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"WAIT","duration":0.5}'

curl -fsS "$PROXY_BASE/v1/browser/screenshot" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -o ./after-typing.png
```

Focus matters: if the wrong window is active, keystrokes go elsewhere. See `POST /v1/browser/actions` in the merged Swagger spec for `CLICK`, `SCROLL`, `HOTKEY`, etc.

### 5) Run a longer CLI (install tools, agents, or one-shot scripts)

**Goal:** Use the sandbox like a remote machine: chain installs or run CLIs, with enough **time** budget.

`POST /v1/shell/exec` accepts an optional **`timeout`** (seconds) for slow commands. What is installed (`node`, `pip`, vendor CLIs) depends on your **image** — check your template or run `which node`, `python3 --version`, and so on first.

```bash
curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"python3 -c \"print(sum(range(1,101)))\"","exec_dir":"/tmp"}'

curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \
  -H "Authorization: Bearer $TREADSTONE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"command":"command -v npx >/dev/null && npx -y cowsay@1.5.0 \"Shipped from the sandbox\" || echo \"npx not available in this image\"","exec_dir":"/tmp","timeout":120}'
```

For products like **Claude Code** or other vendor CLIs, follow their official install steps **inside** the same shell (often `npm install -g …` or a curl installer), set **`timeout`** generously, then invoke the binary from a **subsequent** `exec` once `PATH` is updated. Do not pipe `curl | bash` from docs you do not trust.

Rules that do not change:

- **Only** `Authorization: Bearer <api_key>` — **not** a Console session cookie.
- If your key uses **`selected`** scope for the proxy, it must include this **`sandbox_id`**.
- **WebSocket**: same URL family; use the Bearer header, or `?token=sk-…` if the client cannot set WS headers (see [API Reference](/docs/api-reference.md#proxy)).

## MCP

If your workload speaks MCP, use **`urls.mcp`** from the same sandbox response (full URL to the MCP path). Config examples and client files live in [MCP in sandbox](/docs/mcp-sandbox.md).

## Browser workspace vs proxy

**`urls.web`** is for humans in a browser (session or handoff). Automation into **HTTP services** should use **`urls.proxy`** / **`urls.mcp`**, not `urls.web`, unless you deliberately use a browser flow — see [Browser Handoff](/docs/browser-handoff.md).

## Explore the contract

The hosted [Swagger UI](https://api.treadstone-ai.dev/docs) includes **merged** sandbox-runtime paths under `/v1/sandboxes/{sandbox_id}/proxy/...` so you can inspect REST shapes for traffic into the box. The Python SDK is generated from a different export; see [REST API Guide](/docs/rest-api-guide.md#discovering-the-contract).

## Read next

- [REST API Guide](/docs/rest-api-guide.md) — headers, errors, `curl`/httpx
- [MCP in sandbox](/docs/mcp-sandbox.md) — MCP-specific setup
- [API Reference](/docs/api-reference.md) — Proxy, **Sandbox runtime (shell, …)**, and route tables
- [Sandbox endpoints](/docs/sandbox-endpoints.md) — Web / MCP / Proxy in the Console
- [API Keys & Auth](/docs/api-keys-auth.md) — scope and least privilege
