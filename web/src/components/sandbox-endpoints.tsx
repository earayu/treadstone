import { Copy, ExternalLink } from "lucide-react"
import { toast } from "sonner"

import type { Sandbox } from "@/api/sandboxes"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { DOCS_SANDBOX_ENDPOINTS, buildMcpClientConfigJson } from "@/lib/sandbox-endpoints-meta"
import { cn } from "@/lib/utils"

const ENDPOINT_TOOLTIP_WEB = `For humans: opens in your browser so you can use the built-in Chrome, VS Code, Terminal, Jupyter, and other tools inside the sandbox. Click opens this URL in a new tab. Full reference: ${DOCS_SANDBOX_ENDPOINTS}`

const ENDPOINT_TOOLTIP_MCP = `For AI assistants: MCP clients connect here to work inside the sandbox—browser automation, VS Code, Share, and more. Click copies a sample mcp.json-style snippet (url + Authorization header). Replace the placeholder with an API key from Settings → API Keys. Full reference: ${DOCS_SANDBOX_ENDPOINTS}`

const ENDPOINT_TOOLTIP_PROXY = `HTTP access to the sandbox runtime. Send requests with your API key. Click copies the URL. Full reference: ${DOCS_SANDBOX_ENDPOINTS}`

function compactUrlDisplay(url: string): string {
  try {
    const u = new URL(url)
    const host = u.hostname
    const path = u.pathname + u.search
    const tail = path && path !== "/" ? path : ""
    const combined = tail ? `${host}${tail}` : host
    return combined.length > 52 ? `${combined.slice(0, 49)}…` : combined
  } catch {
    return url.length > 52 ? `${url.slice(0, 49)}…` : url
  }
}

async function copyToClipboard(text: string, successMessage: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(successMessage)
  } catch {
    toast.error("Could not copy to clipboard.")
  }
}

function EndpointWebRow({ href, display }: { href: string; display: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          title={href}
          className="group flex min-w-0 items-center gap-2 rounded-sm py-0.5 transition-colors [-webkit-tap-highlight-color:transparent] hover:bg-muted/25 active:-translate-y-px"
        >
          <span className="shrink-0 rounded border border-primary/35 bg-primary/5 px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-widest text-primary">
            WEB
          </span>
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground transition-colors group-hover:text-foreground">
            {display}
          </span>
          <ExternalLink
            className="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            strokeWidth={1.5}
            aria-hidden
          />
        </a>
      </TooltipTrigger>
      <TooltipContent side="left" className="max-w-[min(22rem,calc(100vw-2rem))] leading-relaxed">
        <p>{ENDPOINT_TOOLTIP_WEB}</p>
      </TooltipContent>
    </Tooltip>
  )
}

function EndpointCopyRow({
  kind,
  url,
  display,
  tooltip,
  labelClassName,
  copyText,
  copySuccessMessage,
}: {
  kind: "PROXY" | "MCP"
  url: string
  display: string
  tooltip: string
  labelClassName: string
  /** When set, this is copied instead of `url` (e.g. MCP client JSON). */
  copyText?: string
  copySuccessMessage?: string
}) {
  const label = kind === "MCP" ? "MCP" : "PROXY"
  const textToCopy = copyText ?? url
  const successMessage = copySuccessMessage ?? "Copied to clipboard."
  const ariaLabel =
    kind === "MCP" && copyText
      ? "Copy MCP server configuration JSON"
      : `Copy ${label} URL`
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={() => void copyToClipboard(textToCopy, successMessage)}
          title={url}
          aria-label={ariaLabel}
          className="group flex w-full min-w-0 cursor-pointer items-center gap-2 rounded-sm py-0.5 text-left transition-colors [-webkit-tap-highlight-color:transparent] hover:bg-muted/25 active:-translate-y-px"
        >
          <span
            className={cn(
              "shrink-0 rounded border px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-widest",
              labelClassName,
            )}
          >
            {label}
          </span>
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground transition-colors group-hover:text-foreground">
            {display}
          </span>
          <Copy
            className="size-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            strokeWidth={1.5}
            aria-hidden
          />
        </button>
      </TooltipTrigger>
      <TooltipContent side="left" className="max-w-[min(22rem,calc(100vw-2rem))] leading-relaxed">
        <p>{tooltip}</p>
      </TooltipContent>
    </Tooltip>
  )
}

export function SandboxEndpointsCell({ sandbox, className }: { sandbox: Sandbox; className?: string }) {
  const urls = sandbox.urls
  if (!urls?.proxy) {
    return <span className="text-xs text-muted-foreground/40">—</span>
  }
  const webDisplay = urls.web
    ? (() => {
        const w = urls.web
        try {
          return new URL(w).hostname
        } catch {
          return compactUrlDisplay(w)
        }
      })()
    : null
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      {urls.web ? <EndpointWebRow href={urls.web} display={webDisplay ?? compactUrlDisplay(urls.web)} /> : null}
      {urls.mcp ? (
        <EndpointCopyRow
          kind="MCP"
          url={urls.mcp}
          display={compactUrlDisplay(urls.mcp)}
          tooltip={ENDPOINT_TOOLTIP_MCP}
          labelClassName="border-slate-500/30 text-slate-500 dark:text-slate-400"
          copyText={buildMcpClientConfigJson(urls.mcp, `treadstone-${sandbox.id}`)}
          copySuccessMessage="Copied MCP config. Replace the API key placeholder with a key from Settings → API Keys."
        />
      ) : null}
      <EndpointCopyRow
        kind="PROXY"
        url={urls.proxy}
        display={compactUrlDisplay(urls.proxy)}
        tooltip={ENDPOINT_TOOLTIP_PROXY}
        labelClassName="border-border/50 bg-muted/15 text-muted-foreground"
      />
    </div>
  )
}
