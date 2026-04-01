/**
 * In-app documentation URLs for the Console (`/docs/{slug}` + optional `#anchor`).
 * Anchors must match `slugifyHeading` in `web/src/pages/public/docs.tsx`
 * (lowercase words joined by hyphens; punctuation stripped).
 */
export const DOC = {
  sandboxLifecycle: {
    inTheConsole: "/docs/sandbox-lifecycle#in-the-console",
    keyFields: "/docs/sandbox-lifecycle#key-fields",
    /** Heading `## Stop & Start` → id `stop--start` */
    stopStart: "/docs/sandbox-lifecycle#stop--start",
  },
  sandboxEndpoints: {
    controlPlaneVsDataPlane: "/docs/sandbox-endpoints#control-plane-vs-data-plane",
  },
  quickstart: {
    shortestPath: "/docs/quickstart#shortest-path",
  },
  apiKeysAuth: {
    inTheConsole: "/docs/api-keys-auth#in-the-console",
    sessionsVsApiKeys: "/docs/api-keys-auth#sessions-vs-api-keys",
    scopeDataPlane: "/docs/api-keys-auth#scope-a-key-to-the-data-plane",
  },
  usageLimits: {
    whatIsCu: "/docs/usage-limits#what-is-a-compute-unit",
    budget: "/docs/usage-limits#how-the-budget-works",
    controllingConsumption: "/docs/usage-limits#controlling-consumption",
    checkingBalance: "/docs/usage-limits#checking-your-balance",
  },
  browserHandoff: {
    howToUseWebUrl: "/docs/browser-handoff#how-to-use-the-web-url",
    revokeAndRefresh: "/docs/browser-handoff#revoke-and-refresh",
  },
  restApiGuide: {
    dataPlaneProxy: "/docs/rest-api-guide#how-to-use-the-data-plane-proxy",
    /** `### cURL` under “How to use the data-plane proxy” */
    curlExample: "/docs/rest-api-guide#curl",
  },
  /** Heading `## How to use (MCP client config)` → `how-to-use-mcp-client-config` */
  mcpSandbox: {
    clientConfig: "/docs/mcp-sandbox#how-to-use-mcp-client-config",
  },
  /** `## Hands-on examples` — shell/file/browser via proxy */
  insideSandbox: {
    handsOnExamples: "/docs/inside-sandbox#hands-on-examples",
    /** `### 5) Run a longer CLI (install tools, agents, or one-shot scripts)` */
    shellLongCli: "/docs/inside-sandbox#5-run-a-longer-cli-install-tools-agents-or-one-shot-scripts",
  },
} as const
