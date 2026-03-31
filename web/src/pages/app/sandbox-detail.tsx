import { useMemo, useState } from "react"
import * as Dialog from "@radix-ui/react-dialog"
import { useNavigate, useParams } from "react-router"
import { X, Copy, RefreshCw, Trash2 } from "lucide-react"
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

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-border/10 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <span className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
        {label}
      </span>
      <div className="min-w-0 flex-1 text-sm text-foreground sm:text-right">{children}</div>
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
  const [open, setOpen] = useState(true)

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

  const handleOpenChange = (next: boolean) => {
    setOpen(next)
    if (!next) navigate("/app")
  }

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
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[min(100vw-2rem,520px)] -translate-x-1/2 -translate-y-1/2",
            "border border-border/20 bg-card shadow-xl outline-none",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            "flex flex-col overflow-hidden",
          )}
        >
          <div className="flex items-center justify-between border-b border-border/15 px-6 py-4">
            <Dialog.Title className="text-lg font-bold tracking-tight text-foreground">
              Sandbox Detail
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              Sandbox configuration, browser hand-off URLs, and lifecycle actions.
            </Dialog.Description>
            <Dialog.Close
              className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              aria-label="Close"
            >
              <X className="size-5" />
            </Dialog.Close>
          </div>

          <div className="overflow-y-auto px-6 py-4">
            {isLoading && (
              <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
            )}
            {isError && (
              <p className="py-8 text-center text-sm text-destructive">
                {error instanceof Error ? error.message : "Failed to load sandbox."}
              </p>
            )}
            {sandbox && (
              <>
                <div className="mb-6 flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "inline-block size-2 rounded-full",
                        isReady && "bg-primary",
                        isCreating && "bg-amber-500",
                        !isReady && !isCreating && "bg-muted-foreground/50",
                      )}
                    />
                    <span className="text-sm font-semibold text-foreground">
                      {isReady ? "Running" : sandbox.status}
                    </span>
                  </div>
                  <span className="text-sm text-muted-foreground">·</span>
                  <span className="text-sm text-muted-foreground">{sandbox.template}</span>
                  <span className="text-sm text-muted-foreground">·</span>
                  <span className="text-sm text-muted-foreground">
                    Started {formatRelativeTime(sandbox.started_at ?? undefined)}
                  </span>
                </div>

                <div className="border-t border-border/10">
                  <Row label="Sandbox ID">
                    <span className="font-mono text-xs break-all">{sandbox.id}</span>
                  </Row>
                  <Row label="Name">{sandbox.name || "—"}</Row>
                  <Row label="Template">
                    <span className="text-muted-foreground">{templateSpec}</span>
                  </Row>
                  <Row label="Status">
                    <span className="capitalize">{sandbox.status}</span>
                  </Row>
                  <Row label="Labels">{labelsToString(sandbox.labels)}</Row>
                  <Row label="Auto-stop">{formatMinutes(sandbox.auto_stop_interval)} inactivity</Row>
                  <Row label="Auto-delete">
                    {sandbox.auto_delete_interval === -1
                      ? "Off"
                      : `${formatMinutes(sandbox.auto_delete_interval)} after stop`}
                  </Row>
                  <Row label="Persist">{sandbox.persist ? "Yes" : "No"}</Row>
                  <Row label="Storage">{sandbox.storage_size ?? "—"}</Row>
                  <Row label="Created">{formatDateTime(sandbox.created_at)}</Row>
                  <Row label="Started">{formatDateTime(sandbox.started_at)}</Row>
                </div>

                <div className="mt-8">
                  <h3 className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                    Browser hand-off
                  </h3>
                  <div className="mt-3 space-y-3 rounded border border-border/15 bg-background/40 p-4">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                          Web URL
                        </p>
                        <div className="flex items-center gap-1">
                          {sandbox.urls?.web && (
                            <button
                              type="button"
                              onClick={() => {
                                void navigator.clipboard.writeText(sandbox.urls!.web!)
                                toast.success("Copied!")
                              }}
                              title="Copy web URL"
                              className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                            >
                              <Copy className="size-3" />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => void handleRecreateLink()}
                            title="Recreate link"
                            className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            <RefreshCw className="size-3" />
                          </button>
                          {webLink?.enabled && (
                            <button
                              type="button"
                              onClick={() => void handleDeleteLink()}
                              title="Delete link"
                              className="rounded p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                            >
                              <Trash2 className="size-3" />
                            </button>
                          )}
                        </div>
                      </div>
                      {sandbox.urls?.web ? (
                        <a
                          href={sandbox.urls.web}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 block font-mono text-xs text-primary hover:underline break-all"
                        >
                          {sandbox.urls.web}
                        </a>
                      ) : (
                        <p className="mt-1 text-xs text-muted-foreground">—</p>
                      )}
                    </div>
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
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
                            className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                          >
                            <Copy className="size-3" />
                          </button>
                        )}
                      </div>
                      <p className="mt-1 font-mono text-xs break-all text-muted-foreground">
                        {sandbox.urls?.proxy ?? "—"}
                      </p>
                    </div>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                          Link expires
                        </p>
                        <p className="mt-1 text-xs text-foreground">
                          {webLink?.expires_at ? formatDateTime(webLink.expires_at) : "Never"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                          Last used
                        </p>
                        <p className="mt-1 text-xs text-foreground">
                          {formatDateTime(webLink?.last_used_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

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
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
