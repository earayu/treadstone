# Sandbox endpoints

## What this page is for

In the Console, each sandbox row can show three links under Endpoints: Web, MCP, and Proxy. Those are the same three strings you get back under `urls` when you fetch that sandbox over the API or CLI.

![Sandboxes table row: Endpoints column with Web, MCP, and Proxy](/docs/images/sandboxes-endpoints-column.png)

## Where the three URLs come from

You do not compose these strings by hand. They are returned on sandbox detail: `GET /v1/sandboxes/{sandbox_id}`, or the equivalent `treadstone sandboxes get <sandbox_id>`. The Console reads the same `urls` object. For structured CLI output, see the [CLI Guide](/docs/cli-guide.md).

The JSON below is a realistic shape; some fields are omitted, and the token in `urls.web` is truncated. Real handoff tokens are longer and short-lived.

```bash
$ treadstone sandboxes get sb_docexample01
```

```json
{
  "id": "sb_docexample01",
  "name": "demo",
  "template": "aio-sandbox-tiny",
  "status": "stopped",
  "auto_stop_interval": 15,
  "auto_delete_interval": -1,
  "urls": {
    "proxy": "https://api.treadstone-ai.dev/v1/sandboxes/sb_docexample01/proxy",
    "mcp": "https://api.treadstone-ai.dev/v1/sandboxes/sb_docexample01/proxy/mcp",
    "web": "https://sandbox-sb_docexample01.treadstone-ai.dev/_treadstone/open?token=swl…"
  },
  "created_at": "2026-03-31T20:51:22Z",
  "stopped_at": "2026-03-31T21:06:49Z"
}
```

### Web (`urls.web`)

This is the browser entry to the workspace. The path may include `/_treadstone/open` and a token while a handoff session is active. In the table, Web opens in a new tab. Step-by-step usage, shareable links, and how that differs from `web_url` / `open_link` are covered in [Browser Handoff](/docs/browser-handoff.md#how-to-use-the-web-url).

### MCP (`urls.mcp`)

MCP clients connect to this URL to run tools inside the sandbox. Requests use an API key on the data plane, not a Console cookie. In the table, MCP copies the URL so you can paste it into your client. For a sample remote MCP config and where client config files usually live, see [MCP in sandbox](/docs/mcp-sandbox.md#how-to-use-mcp-client-config).

### Proxy (`urls.proxy`)

This is the HTTP gateway prefix into the sandbox: you append the path your app serves, and you send `Authorization: Bearer` with an API key. In the table, Proxy copies that base URL. For cURL and Python examples, see [How to use the data-plane proxy](/docs/rest-api-guide.md#how-to-use-the-data-plane-proxy).

MCP is served on the same reverse-proxy path family as the rest of the data plane (typically `…/proxy/mcp` next to `…/proxy`). It is not a second platform. Protocol details live in [MCP in sandbox](/docs/mcp-sandbox.md).

Always copy hostnames and paths from the API, the CLI, or the Console. Guessing breaks quickly.

## Control plane vs data plane

The control plane is the Treadstone API at `https://api.treadstone-ai.dev/v1/...` on the hosted product: sign-in, keys, templates, sandbox lifecycle, usage, issuing handoff links. You can drive it with the CLI, raw HTTP, or the Python SDK; self-hosted installs use their own origin with the same `/v1/...` layout.

The data plane is traffic into a running sandbox: `urls.proxy` and `urls.mcp` sit on that API host under `/v1/sandboxes/{id}/proxy/...`. Automation must use API keys. Session cookies from the browser do not replace keys here. More on credentials: [API Keys & Auth](/docs/api-keys-auth.md). REST-only framing: [REST API Guide](/docs/rest-api-guide.md).

## Related fields

`web_url` and `open_link` show up in handoff flows and are easy to confuse with `urls.web` when you only read field names. See [Browser Handoff](/docs/browser-handoff.md).

## Read next

- [Inside your sandbox](/docs/inside-sandbox.md)
- [REST API Guide](/docs/rest-api-guide.md)
- [API Keys & Auth](/docs/api-keys-auth.md)
- [MCP in sandbox](/docs/mcp-sandbox.md)
- [Browser Handoff](/docs/browser-handoff.md)
- [Sandbox Lifecycle](/docs/sandbox-lifecycle.md)
