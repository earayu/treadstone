import { useMemo } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { Copy, ExternalLink, Package, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  useSandbox,
  useDeleteSandbox,
  useStartSandbox,
  useStopSandbox,
} from "@/api/sandboxes"
import { useSandboxTemplates } from "@/api/templates"
import { client } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { formatMinutes } from "@/lib/format-time"
import type { components } from "@/api/schema"

type SandboxDetail = components["schemas"]["SandboxDetailResponse"]
type WebLinkStatus = components["schemas"]["SandboxWebLinkStatusResponse"]

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  const diffMs = now - then
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
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

function labelsToString(labels: SandboxDetail["labels"]): string {
  if (!labels || typeof labels !== "object") return "—"
  const entries = Object.entries(labels as Record<string, unknown>)
  if (entries.length === 0) return "—"
  return entries.map(([k, v]) => `${k}: ${String(v)}`).join(", ")
}

function ConfigField({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">{label}</p>
      <div className="mt-2 text-sm text-foreground">{children}</div>
    </div>
  )
}

export function SandboxDetailPage() {
  const { id = "" } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: sandbox, isLoading, isError, error } = useSandbox(id)
  const { data: templatesData } = useSandboxTemplates()
  const deleteSandbox = useDeleteSandbox()
  const stopSandbox = useStopSandbox()
  const startSandbox = useStartSandbox()

  const { data: webLink } = useQuery({
    queryKey: ["sandboxes", id, "web-link"],
    queryFn: async () => {
      try {
        const { data } = await client.GET("/v1/sandboxes/{sandbox_id}/web-link", {
          params: { path: { sandbox_id: id } },
        })
        return data as WebLinkStatus
      } catch {
        return null
      }
    },
    enabled: !!id,
    retry: false,
  })

  const templateSpec = useMemo(() => {
    if (!sandbox) return null
    const t = templatesData?.items?.find((x) => x.name === sandbox.template)
    if (!t) return sandbox.template
    return `${t.display_name} · ${t.resource_spec.cpu} CPU · ${t.resource_spec.memory}`
  }, [sandbox, templatesData?.items])

  const pageTitle = sandbox
    ? sandbox.name?.trim() || sandbox.id
    : id
    ? `Sandbox ${id}`
    : "Sandbox"

  const isReady = sandbox?.status === "ready"
  const isCreating = sandbox?.status === "creating"
  const canStart = sandbox?.status === "stopped" || sandbox?.status === "error"
  const canDelete =
    sandbox?.status === "creating" ||
    sandbox?.status === "stopped" ||
    sandbox?.status === "error"

  async function handleRecreateLink() {
    if (!id) return
    try {
      await client.POST("/v1/sandboxes/{sandbox_id}/web-link", {
        params: { path: { sandbox_id: id } },
      })
      await qc.invalidateQueries({ queryKey: ["sandboxes", id] })
      await qc.invalidateQueries({ queryKey: ["sandboxes", id, "web-link"] })
      toast.success("Web link recreated.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to recreate link.")
    }
  }

  async function handleDeleteLink() {
    if (!id) return
    if (!window.confirm("Delete this web link?")) return
    try {
      await client.DELETE("/v1/sandboxes/{sandbox_id}/web-link", {
        params: { path: { sandbox_id: id } },
      })
      await qc.invalidateQueries({ queryKey: ["sandboxes", id] })
      await qc.invalidateQueries({ queryKey: ["sandboxes", id, "web-link"] })
      toast.success("Web link deleted.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete link.")
    }
  }

  async function handleStop() {
    if (!id) return
    try {
      await stopSandbox.mutateAsync(id)
      toast.success("Sandbox stopped.")
      await qc.invalidateQueries({ queryKey: ["sandboxes", id] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to stop sandbox.")
    }
  }

  async function handleStart() {
    if (!id) return
    try {
      await startSandbox.mutateAsync(id)
      toast.success("Starting sandbox…")
      await qc.invalidateQueries({ queryKey: ["sandboxes", id] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start sandbox.")
    }
  }

  async function handleDelete() {
    if (!id || !sandbox) return
    const confirmMsg =
      sandbox.status === "creating"
        ? "Cancel provisioning and delete this sandbox permanently?"
        : "Delete this sandbox permanently?"
    if (!window.confirm(confirmMsg)) return
    try {
      await deleteSandbox.mutateAsync(id)
      toast.success("Sandbox deleted.")
      navigate("/app")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete sandbox.")
    }
  }

  return (
    <div className="pb-16">
      <Link
        to="/app"
        className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <span aria-hidden>←</span> Back to sandboxes
      </Link>

      <div className="mt-6 lg:grid lg:grid-cols-[1fr_minmax(260px,300px)] lg:items-start lg:gap-10">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{pageTitle}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {sandbox
              ? "Sandbox details, access URLs, and lifecycle controls."
              : isLoading
                ? "Loading sandbox…"
                : "Sandbox environment"}
          </p>

          {sandbox && (
            <div className="mt-6 flex flex-wrap items-center gap-3 border border-border/30 bg-card/70 px-4 py-3">
              <span
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold",
                  isReady && "border-primary/40 bg-primary/10 text-foreground",
                  isCreating && "border-amber-500/40 bg-amber-500/10 text-foreground",
                  !isReady && !isCreating && "border-border/50 bg-muted/30 text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "inline-block size-1.5 rounded-full",
                    isReady && "bg-primary",
                    isCreating && "bg-amber-500",
                    !isReady && !isCreating && "bg-muted-foreground/60",
                  )}
                />
                <span className="capitalize">{isReady ? "Running" : sandbox.status}</span>
              </span>
              <span className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground/90">{sandbox.template}</span>
                <span aria-hidden className="mx-2 text-border">
                  ·
                </span>
                Started {formatRelativeTime(sandbox.started_at ?? undefined)}
              </span>
            </div>
          )}

          <div className="mt-8">
            {isLoading && (
              <p className="py-12 text-center text-sm text-muted-foreground">Loading…</p>
            )}
            {isError && (
              <p className="rounded border border-destructive/30 bg-destructive/5 py-8 text-center text-sm text-destructive">
                {error instanceof Error ? error.message : "Failed to load sandbox."}
              </p>
            )}
            {sandbox && (
              <>
                <section className="space-y-8" aria-labelledby="sandbox-config-heading">
                  <div>
                    <h2
                      id="sandbox-config-heading"
                      className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                    >
                      Configuration
                    </h2>
                    <div className="mt-4 border border-border/30 bg-card/70 p-6">
                      <div className="grid gap-8 sm:grid-cols-2">
                        <ConfigField label="Sandbox ID">
                          <span className="font-mono text-xs break-all">{sandbox.id}</span>
                        </ConfigField>
                        <ConfigField label="Name">{sandbox.name || "—"}</ConfigField>
                        <ConfigField label="Template">
                          <span className="text-muted-foreground">{templateSpec}</span>
                        </ConfigField>
                        <ConfigField label="Status">
                          <span className="capitalize">{sandbox.status}</span>
                        </ConfigField>
                        <ConfigField label="Labels" className="sm:col-span-2">
                          {labelsToString(sandbox.labels)}
                        </ConfigField>
                        <ConfigField label="Auto-stop">
                          {formatMinutes(sandbox.auto_stop_interval)} inactivity
                        </ConfigField>
                        <ConfigField label="Auto-delete">
                          {sandbox.auto_delete_interval === -1
                            ? "Off"
                            : `${formatMinutes(sandbox.auto_delete_interval)} after stop`}
                        </ConfigField>
                        <ConfigField label="Persist">{sandbox.persist ? "Yes" : "No"}</ConfigField>
                        <ConfigField label="Storage">{sandbox.storage_size ?? "—"}</ConfigField>
                        <ConfigField label="Created">{formatDateTime(sandbox.created_at)}</ConfigField>
                        <ConfigField label="Started">{formatDateTime(sandbox.started_at)}</ConfigField>
                      </div>
                    </div>
                  </div>

                  <div aria-labelledby="sandbox-handoff-heading">
                    <h2
                      id="sandbox-handoff-heading"
                      className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                    >
                      Browser hand-off
                    </h2>
                    <div className="mt-4 space-y-6 border border-border/30 bg-card/70 p-6">
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                            Web URL
                          </p>
                          <div className="flex items-center gap-0.5">
                            {sandbox.urls?.web && (
                              <>
                                <a
                                  href={sandbox.urls.web}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  title="Open in new tab"
                                  className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                >
                                  <ExternalLink className="size-3.5" />
                                </a>
                                <button
                                  type="button"
                                  onClick={() => {
                                    void navigator.clipboard.writeText(sandbox.urls!.web!)
                                    toast.success("Copied!")
                                  }}
                                  title="Copy web URL"
                                  className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                >
                                  <Copy className="size-3.5" />
                                </button>
                              </>
                            )}
                            <button
                              type="button"
                              onClick={() => void handleRecreateLink()}
                              title="Recreate link"
                              className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                            >
                              <RefreshCw className="size-3.5" />
                            </button>
                            {webLink?.enabled && (
                              <button
                                type="button"
                                onClick={() => void handleDeleteLink()}
                                title="Delete link"
                                className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                        {sandbox.urls?.web ? (
                          <a
                            href={sandbox.urls.web}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 block break-all font-mono text-xs text-primary hover:underline"
                          >
                            {sandbox.urls.web}
                          </a>
                        ) : (
                          <p className="mt-2 text-xs text-muted-foreground">—</p>
                        )}
                      </div>

                      <div className="border-t border-border/20 pt-6">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                            Proxy URL
                          </p>
                          {sandbox.urls?.proxy && (
                            <button
                              type="button"
                              onClick={() => {
                                void navigator.clipboard.writeText(sandbox.urls!.proxy!)
                                toast.success("Copied!")
                              }}
                              title="Copy proxy URL"
                              className="rounded p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                            >
                              <Copy className="size-3.5" />
                            </button>
                          )}
                        </div>
                        <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                          {sandbox.urls?.proxy ?? "—"}
                        </p>
                      </div>

                      <div className="grid gap-6 border-t border-border/20 pt-6 sm:grid-cols-2">
                        <ConfigField label="Link expires">
                          {webLink?.expires_at ? formatDateTime(webLink.expires_at) : "Never"}
                        </ConfigField>
                        <ConfigField label="Last used">{formatDateTime(webLink?.last_used_at)}</ConfigField>
                      </div>
                    </div>
                  </div>
                </section>

                <div className="mt-8 flex flex-wrap items-center gap-2">
                  {isReady && (
                    <button
                      type="button"
                      onClick={() => void handleStop()}
                      disabled={stopSandbox.isPending}
                      className="border border-border/40 bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 disabled:opacity-40"
                    >
                      Stop
                    </button>
                  )}
                  {isCreating && (
                    <span
                      role="status"
                      aria-live="polite"
                      className="border border-border/40 bg-secondary/50 px-4 py-2 text-sm font-medium text-muted-foreground"
                    >
                      Provisioning…
                    </span>
                  )}
                  {canStart && (
                    <button
                      type="button"
                      onClick={() => void handleStart()}
                      disabled={startSandbox.isPending}
                      className="border border-border/40 bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 disabled:opacity-40"
                    >
                      Start
                    </button>
                  )}
                  {canDelete && (
                    <button
                      type="button"
                      onClick={() => void handleDelete()}
                      disabled={deleteSandbox.isPending}
                      className="bg-destructive px-4 py-2 text-sm font-bold text-destructive-foreground transition-colors hover:bg-destructive/90 disabled:opacity-50"
                    >
                      {isCreating ? "Cancel provisioning" : "Delete"}
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <aside className="mt-10 lg:mt-0">
          <div className="border border-border/15 bg-card p-6">
            <div className="flex items-start gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center border border-border/40 bg-background/60">
                <Package className="size-4 text-primary" aria-hidden />
              </span>
              <div className="min-w-0">
                <h2 className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                  Apps & extensions
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  This column is reserved for sandbox add-ons: install tools, run one-click actions against the sandbox
                  API, and wire up workflows like Claude Code—without leaving the console.
                </p>
              </div>
            </div>
            <div className="mt-6 border border-dashed border-border/50 bg-muted/20 px-4 py-8 text-center">
              <p className="text-xs font-medium text-foreground/80">Nothing installed yet</p>
              <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                Extensions will appear here when available.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
