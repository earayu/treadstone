import type { ReactNode } from "react"
import { ChevronRight, Copy, RefreshCw, Trash2 } from "lucide-react"
import { Link } from "react-router"
import { toast } from "sonner"

import type { Sandbox } from "@/api/sandboxes"
import { DOC } from "@/lib/console-docs"
import { buildMcpClientConfigJson } from "@/lib/sandbox-endpoints-meta"
import type { components } from "@/api/schema"

type WebLinkStatus = components["schemas"]["SandboxWebLinkStatusResponse"]

async function copyToClipboard(text: string, successMessage: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(successMessage)
  } catch {
    toast.error("Could not copy to clipboard.")
  }
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    })
  } catch {
    return iso
  }
}

function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground/70">{children}</p>
  )
}

function DocLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      to={href}
      className="group inline-flex items-center gap-0.5 text-xs text-primary/80 transition-colors hover:text-primary"
    >
      {children}
      <ChevronRight className="size-3 opacity-50 transition-transform group-hover:translate-x-0.5" strokeWidth={2} aria-hidden />
    </Link>
  )
}

/** A dark code/pre block with an optional copy action in the header. */
function CodeBlock({
  children,
  "aria-label": ariaLabel,
  language = "bash",
  onCopy,
}: {
  children: string
  "aria-label"?: string
  language?: string
  onCopy?: () => void
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border/40">
      <div className="flex items-center justify-between border-b border-white/5 bg-zinc-900 px-3.5 py-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">{language}</span>
        {onCopy && (
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-medium text-zinc-400 transition-colors hover:bg-white/8 hover:text-zinc-200 active:scale-95"
          >
            <Copy className="size-3" aria-hidden />
            Copy
          </button>
        )}
      </div>
      <pre
        aria-label={ariaLabel}
        className="max-h-[min(24rem,50vh)] overflow-auto bg-zinc-950 px-4 py-3.5 font-mono text-[11px] leading-relaxed tracking-tight text-zinc-300"
      >
        {children}
      </pre>
    </div>
  )
}

/** A single endpoint section — badge + title + description + optional doc link + content. */
function EndpointSection({
  id,
  badge,
  title,
  description,
  docHref,
  docLabel,
  children,
}: {
  id: string
  badge: string
  title: string
  description: ReactNode
  docHref?: string
  docLabel?: string
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className="scroll-mt-24 space-y-4 border-t border-border/20 pt-6 first:border-t-0 first:pt-0"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="rounded border border-border/50 bg-muted/40 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {badge}
            </span>
            <h3 id={`${id}-heading`} className="text-sm font-semibold tracking-tight text-foreground">
              {title}
            </h3>
          </div>
          <p className="max-w-[62ch] text-xs leading-relaxed text-muted-foreground">{description}</p>
        </div>
        {docHref && docLabel && (
          <div className="shrink-0 pt-0.5">
            <DocLink href={docHref}>{docLabel}</DocLink>
          </div>
        )}
      </div>

      <div className="space-y-4">{children}</div>
    </section>
  )
}

export function SandboxEndpointsDetail({
  sandbox,
  webLink,
  onRecreateLink,
  onDeleteLink,
}: {
  sandbox: Sandbox
  webLink: WebLinkStatus | null | undefined
  onRecreateLink: () => void | Promise<void>
  onDeleteLink: () => void | Promise<void>
}) {
  const urls = sandbox.urls
  const proxyBase = urls?.proxy ?? ""
  const webUrl = urls?.web
  const mcpUrl = urls?.mcp

  const mcpJson =
    mcpUrl != null && mcpUrl !== ""
      ? buildMcpClientConfigJson(mcpUrl, `treadstone-${sandbox.id}`)
      : ""

  const proxyCurl = proxyBase
    ? [
        "# Replace TREADSTONE_API_KEY with an API key from Settings → API Keys.",
        'export TREADSTONE_API_KEY="sk_..."',
        `export PROXY_BASE="${proxyBase}"`,
        "",
        'curl -sS "$PROXY_BASE/health" \\',
        '  -H "Authorization: Bearer $TREADSTONE_API_KEY"',
      ].join("\n")
    : ""

  /** POST /v1/shell/exec — command runs inside the sandbox via the data-plane proxy (not on your laptop). */
  const claudeInstallShellExecCurl = proxyBase
    ? [
        "# Runs inside the sandbox: POST /v1/shell/exec (raise timeout if the installer is slow).",
        'export TREADSTONE_API_KEY="sk_..."',
        `export PROXY_BASE="${proxyBase}"`,
        "",
        'curl -sS -X POST "$PROXY_BASE/v1/shell/exec" \\',
        '  -H "Authorization: Bearer $TREADSTONE_API_KEY" \\',
        '  -H "Content-Type: application/json" \\',
        `  -d '{"command":"curl -fsSL https://claude.ai/install.sh | bash","exec_dir":"/tmp","timeout":600}'`,
      ].join("\n")
    : ""

  return (
    <div className="rounded-xl border border-border/30 bg-card/60 px-5 py-6 sm:px-7 sm:py-7 space-y-6">
      {/* Web / Browser workspace */}
      <EndpointSection
        id="endpoint-web"
        badge="Web"
        title="Browser workspace"
        description="Opens the sandbox in your browser (VS Code, terminal, Jupyter). The URL includes a short-lived token while a session is active."
        docHref={DOC.browserHandoff.howToUseWebUrl}
        docLabel="How to use the Web URL"
      >
        {webUrl ? (
          <>
            <div className="space-y-1.5">
              <FieldLabel>URL</FieldLabel>
              {/* Click to navigate — no icons */}
              <a
                href={webUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block break-all rounded-lg border border-border/40 bg-muted/20 px-3.5 py-2.5 font-mono text-xs leading-relaxed text-primary transition-colors hover:bg-muted/35"
              >
                {webUrl}
              </a>
            </div>

            <div className="space-y-3">
              <FieldLabel>Web session</FieldLabel>
              <p className="text-xs text-muted-foreground">
                Rotate the link if it leaks; delete to revoke.{" "}
                <DocLink href={DOC.browserHandoff.revokeAndRefresh}>Revoke and refresh</DocLink>
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void onRecreateLink()}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border/45 bg-secondary px-3.5 py-1.5 text-xs font-semibold text-secondary-foreground transition-[transform,background-color] hover:bg-secondary/80 active:scale-[0.97]"
                >
                  <RefreshCw className="size-3.5" aria-hidden />
                  Recreate link
                </button>
                {webLink?.enabled && (
                  <button
                    type="button"
                    onClick={() => void onDeleteLink()}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-destructive/8 px-3.5 py-1.5 text-xs font-semibold text-destructive transition-[transform,background-color] hover:bg-destructive/15 active:scale-[0.97]"
                  >
                    <Trash2 className="size-3.5" aria-hidden />
                    Delete link
                  </button>
                )}
              </div>

              <dl className="grid gap-4 border-t border-border/15 pt-3 sm:grid-cols-2">
                <div>
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground/70">
                    Link expires
                  </dt>
                  <dd className="mt-1 font-mono text-xs text-foreground">
                    {webLink?.expires_at ? formatDateTime(webLink.expires_at) : "Never"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[10px] font-semibold uppercase tracking-[0.13em] text-muted-foreground/70">
                    Last used
                  </dt>
                  <dd className="mt-1 font-mono text-xs text-foreground">
                    {formatDateTime(webLink?.last_used_at)}
                  </dd>
                </div>
              </dl>
            </div>
          </>
        ) : (
          <p className="rounded-lg border border-dashed border-border/40 bg-muted/8 px-4 py-5 text-xs text-muted-foreground">
            No Web URL yet — available when the sandbox is ready.
          </p>
        )}
      </EndpointSection>

      {/* MCP */}
      {mcpUrl ? (
        <EndpointSection
          id="endpoint-mcp"
          badge="MCP"
          title="Model Context Protocol"
          description={
            <>
              Paste this JSON into your MCP client (Cursor, Claude Desktop, etc.). Replace the{" "}
              <Link
                to="/app/api-keys"
                className="text-primary underline decoration-primary/35 underline-offset-2 transition-colors hover:text-primary/90 hover:decoration-primary/55"
              >
                API key
              </Link>{" "}
              placeholder with a key from Settings → API Keys.
            </>
          }
          docHref={DOC.mcpSandbox.clientConfig}
          docLabel="MCP client configuration"
        >
          <div className="space-y-1.5">
            <FieldLabel>Client configuration</FieldLabel>
            <CodeBlock
              aria-label="MCP server configuration JSON"
              language="json"
              onCopy={() =>
                void copyToClipboard(
                  mcpJson,
                  "Copied MCP config. Replace the API key placeholder with a key from Settings → API Keys.",
                )
              }
            >
              {mcpJson}
            </CodeBlock>
          </div>
        </EndpointSection>
      ) : null}

      {/* HTTP Proxy */}
      {proxyBase ? (
        <EndpointSection
          id="endpoint-proxy"
          badge="Proxy"
          title="HTTP data plane"
          description="Append your workload path after /proxy. Every request must include Authorization: Bearer with a data-plane API key."
          docHref={DOC.restApiGuide.dataPlaneProxy}
          docLabel="Data-plane proxy (cURL and examples)"
        >
          <div className="space-y-4">
            <div className="space-y-1.5">
              <FieldLabel>Base URL</FieldLabel>
              {/* Click to copy — no icons */}
              <button
                type="button"
                onClick={() => void copyToClipboard(proxyBase, "Copied proxy base URL.")}
                title="Click to copy"
                className="w-full cursor-pointer break-all rounded-lg border border-border/40 bg-muted/15 px-3.5 py-2.5 text-left font-mono text-xs leading-relaxed text-foreground/90 transition-[border-color,background-color] duration-150 ease-out hover:border-border/55 hover:bg-muted/22 active:bg-muted/28"
              >
                {proxyBase}
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <FieldLabel>Example (cURL)</FieldLabel>
                <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                  <Link
                    to={DOC.restApiGuide.dataPlaneProxy}
                    className="text-primary/90 underline decoration-primary/30 underline-offset-2 transition-colors hover:text-primary hover:decoration-primary/55"
                  >
                    View docs
                  </Link>
                  <span aria-hidden className="text-border/80">
                    ·
                  </span>
                  <Link
                    to={DOC.insideSandbox.shellLongCli}
                    className="text-primary/90 underline decoration-primary/30 underline-offset-2 transition-colors hover:text-primary hover:decoration-primary/55"
                  >
                    Execution example
                  </Link>
                  <span aria-hidden className="text-border/80">
                    ·
                  </span>
                  <Link
                    to={DOC.insideSandbox.handsOnExamples}
                    className="text-primary/90 underline decoration-primary/30 underline-offset-2 transition-colors hover:text-primary hover:decoration-primary/55"
                  >
                    Inside sandbox
                  </Link>
                </p>
              </div>
              <CodeBlock
                aria-label="cURL example for sandbox proxy"
                onCopy={() => void copyToClipboard(proxyCurl, "Copied cURL example.")}
              >
                {proxyCurl}
              </CodeBlock>
              <div>
                <FieldLabel>Install Claude Code (shell inside sandbox)</FieldLabel>
                <p className="mt-1 max-w-[62ch] text-xs text-muted-foreground">
                  Sends <code className="font-mono text-[11px]">POST /v1/shell/exec</code> over the proxy so the install
                  runs on the sandbox VM, not your machine. Adjust <code className="font-mono text-[11px]">timeout</code>{" "}
                  if needed. Only use installers you trust.
                </p>
                <div className="mt-2">
                  <CodeBlock
                    aria-label="Install Claude Code inside sandbox via shell exec"
                    language="bash"
                    onCopy={() => void copyToClipboard(claudeInstallShellExecCurl, "Copied shell exec example.")}
                  >
                    {claudeInstallShellExecCurl}
                  </CodeBlock>
                </div>
              </div>
            </div>
          </div>
        </EndpointSection>
      ) : (
        <div className="border-t border-border/20 pt-6">
          <p className="rounded-lg border border-dashed border-border/35 bg-muted/8 px-4 py-5 text-xs text-muted-foreground">
            Proxy URL unavailable — check sandbox status.
          </p>
        </div>
      )}
    </div>
  )
}
