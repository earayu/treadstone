# Sandbox endpoints

## Start here (no API jargon yet)

In the **Console → Sandboxes** table, each running sandbox can show up to **three links** in the **Endpoints** column: **Web**, **MCP**, and **Proxy**. Same order every time: Web on top, then MCP, then Proxy.

- **Web** — For **you in a browser**: open the workspace (Chrome, VS Code, terminal, Jupyter, etc., depending on the template).
- **MCP** — For **AI tools and MCP clients** (IDEs, scripts): paste this URL so the client talks **inside** the sandbox.
- **Proxy** — The **base URL for HTTP** into the sandbox: you append paths your app exposes; you authenticate with an **API key**.

You do **not** need to build these URLs yourself. They come from the platform.

## Where `urls.web`, `urls.mcp`, and `urls.proxy` come from

When you **create or fetch a sandbox** (`GET /v1/sandboxes/{id}` or `treadstone sandboxes get …`), the JSON includes a **`urls`** object. The Console rows use the same three entries:

- **Web** → **`urls.web`** — Browser entry to the workspace UI.
- **MCP** → **`urls.mcp`** — Ready-to-use MCP URL (often ends with `/mcp` on the same gateway as the proxy).
- **Proxy** → **`urls.proxy`** — **Gateway prefix** for HTTP: paths after this are forwarded **into** the container.

If the `urls.*` names feel abstract, use this shorthand:

- **`urls.proxy`** — “**Where I send HTTP to reach the sandbox**” (append your app’s path; use an API key).
- **`urls.mcp`** — “**Where I point an MCP client**” (AI tools; still uses API keys on the data plane).
- **`urls.web`** — “**Where I open the workspace in a browser**.”

MCP is **not** a separate product: it is a **convenient URL** on the same data plane as the proxy.

**Rule:** never guess hostnames or paths. Always copy from the **Console** or read **`urls`** from the API/CLI output.

## Two surfaces (control plane vs data plane)

Treadstone splits behavior into two layers:

### Control plane

The **control plane** is **`https://<api-host>/v1/...`**: sign-in, API keys, templates, create/start/stop/delete sandboxes, usage, handoff links—everything **about** the platform.

**How to use it:** **[CLI](/docs/cli-guide.md)** first for day-to-day work; **[REST](/docs/rest-api-guide.md)** and the **[Python SDK](/docs/python-sdk-guide.md)** expose the same operations.

### Data plane

The **data plane** is how traffic reaches **HTTP services inside a running sandbox**. Treadstone fronts that with a **reverse proxy** (`urls.proxy` and paths under `/v1/sandboxes/{sandbox_id}/proxy/{path}`). The **Proxy** and **MCP** Console rows are **data plane** URLs. **Web** is also a browser entry into that environment.

**How to use it:**

1. **Web UI** — Open **`urls.web`** in a browser (human session).
2. **Automation** — Send **`Authorization: Bearer <api_key>`** to URLs under the proxy. The data plane accepts **API keys only** for scripted access (not Console cookies). See [API Keys & Auth](/docs/api-keys-auth.md).

### MCP (same data plane, AI-friendly URL)

**MCP** is not a third platform. **`urls.mcp`** points at the MCP server **inside** the sandbox (commonly the `/mcp` path on the proxy). Clients use the same **API key** model as other data-plane HTTP. Details: [MCP in sandbox](/docs/mcp-sandbox.md).

**At a glance**

- **Control plane** — `/v1/...` for lifecycle and platform APIs.
- **Data plane** — `urls.proxy` / `urls.mcp` / browser **Web** link for work **inside** the sandbox.

## Console: Web, MCP, and Proxy (detail)

The **Sandboxes** table **Endpoints** column lists up to three rows when the sandbox is running and URLs exist. **Order matches the Console:** Web first, then MCP, then Proxy.

### WEB (`urls.web`)

- **Purpose:** Open the **workspace in the browser** (Chrome, VS Code, terminal, Jupyter, etc.—depends on template).
- **Click:** **Opens** the URL in a new tab.

### MCP (`urls.mcp`)

- **Purpose:** **MCP clients** connect here to run tools **inside** the sandbox.
- **Click:** **Copies** the URL (paste into your MCP client).

### PROXY (`urls.proxy`)

- **Purpose:** **Data-plane base URL** for HTTP: append the path your app serves inside the sandbox; use an **API key**.
- **Click:** **Copies** the URL.

For MCP protocol details (SSE, WebSocket, query forwarding), see [MCP in sandbox](/docs/mcp-sandbox.md).

## Related fields (do not confuse)

- **`web_url`** and **`open_link`** — Browser handoff and sharing; different from treating `urls.web` as “just another string.” See [Browser Handoff](/docs/browser-handoff.md).
- **Subdomain browser URLs** — Sometimes used for browser-only flows; for **unattended MCP**, prefer **`urls.mcp`** / **`urls.proxy`** ([MCP in sandbox](/docs/mcp-sandbox.md)).

## Read next

- [REST API Guide](/docs/rest-api-guide.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [MCP in sandbox](/docs/mcp-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
