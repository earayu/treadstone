/** Docs route (in-app) for sandbox URLs — see `web/public/docs/sandbox-endpoints.md`. */
export const DOCS_SANDBOX_ENDPOINTS = "/docs/sandbox-endpoints"

/** Short help for HelpIcon next to "Sandbox endpoints" headings (aligned with Sandboxes table column). */
export const SANDBOX_ENDPOINTS_HELP =
  "Web: opens the workspace in your browser. MCP: copies a JSON snippet for MCP clients (URL + API key placeholder—replace with a key from Settings → API Keys). Proxy: copy the data-plane base URL for HTTP with your API key."

/** Placeholder for Bearer token; uppercase so it is obvious in pasted JSON. */
const MCP_CONFIG_API_KEY_PLACEHOLDER =
  "PASTE_YOUR_API_KEY_HERE_CREATE_ONE_IN_APP_SETTINGS_API_KEYS"

export function buildMcpClientConfigJson(mcpUrl: string, mcpServerKey: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        [mcpServerKey]: {
          url: mcpUrl,
          headers: {
            Authorization: `Bearer ${MCP_CONFIG_API_KEY_PLACEHOLDER}`,
          },
        },
      },
    },
    null,
    2,
  )
}
