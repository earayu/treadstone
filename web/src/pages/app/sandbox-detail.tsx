import { useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { toast } from "sonner"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import {
  useSandbox,
  useDeleteSandbox,
  useStartSandbox,
  useStopSandbox,
  useUpdateSandbox,
  type Sandbox,
} from "@/api/sandboxes"
import { useSandboxTemplates } from "@/api/templates"
import { useUsageOverview } from "@/api/usage"
import { SandboxEndpointsDetail } from "@/components/sandbox-endpoints-detail"
import { DOC } from "@/lib/console-docs"
import { DOCS_SANDBOX_ENDPOINTS, SANDBOX_ENDPOINTS_HELP } from "@/lib/sandbox-endpoints-meta"
import { HelpIcon } from "@/components/ui/help-icon"
import { client, HttpError } from "@/lib/api-client"
import { formatMinutes } from "@/lib/format-time"
import { formatTierDisplayName } from "@/lib/tier-label"
import { cn } from "@/lib/utils"
import type { components } from "@/api/schema"

type SandboxDetail = components["schemas"]["SandboxDetailResponse"]
type WebLinkStatus = components["schemas"]["SandboxWebLinkStatusResponse"]

const SANDBOX_NAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?$/

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

function labelsToComma(labels: SandboxDetail["labels"]): string {
  if (!labels || typeof labels !== "object") return ""
  const entries = Object.entries(labels as Record<string, unknown>)
  if (entries.length === 0) return ""
  return entries.map(([k, v]) => `${k}=${String(v)}`).join(", ")
}

function parseLabels(raw: string): { ok: true; labels: Record<string, string> } | { ok: false } {
  const trimmed = raw.trim()
  if (!trimmed) return { ok: true, labels: {} }
  const labels: Record<string, string> = {}
  for (const part of trimmed.split(",")) {
    const p = part.trim()
    if (!p) continue
    const eq = p.indexOf("=")
    if (eq <= 0) return { ok: false }
    const key = p.slice(0, eq).trim()
    const value = p.slice(eq + 1).trim()
    if (!key) return { ok: false }
    labels[key] = value
  }
  return { ok: true, labels }
}

function labelsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const ak = Object.keys(a).sort()
  const bk = Object.keys(b).sort()
  if (ak.length !== bk.length) return false
  return ak.every((k) => a[k] === b[k])
}

function ConfigReadonly({
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

function resetSettingsDrafts(s: SandboxDetail) {
  return {
    nameDraft: s.name,
    labelsDraft: labelsToComma(s.labels),
    nameTouched: false,
    autoStopNever: s.auto_stop_interval === 0,
    autoStopMinutes: s.auto_stop_interval === 0 ? "60" : String(s.auto_stop_interval),
    autoDeleteEnabled: s.auto_delete_interval !== -1,
    autoDeleteDays:
      s.auto_delete_interval === -1
        ? "7"
        : String(Math.round(s.auto_delete_interval / (24 * 60))),
  }
}

function autoStopViewLabel(sandbox: SandboxDetail): string {
  if (sandbox.auto_stop_interval === 0) return "Never"
  return `${sandbox.auto_stop_interval} minutes`
}

function autoDeleteViewLabel(sandbox: SandboxDetail): string {
  if (sandbox.auto_delete_interval === -1) return "Off"
  const days = Math.round(sandbox.auto_delete_interval / (24 * 60))
  return `${days} day${days === 1 ? "" : "s"}`
}

function SandboxSettingsEditor({
  sandbox,
  templateSpec,
}: {
  sandbox: SandboxDetail
  templateSpec: string | null
}) {
  const { data: usage } = useUsageOverview()
  const updateSandbox = useUpdateSandbox()

  const [isEditing, setIsEditing] = useState(false)
  const [nameDraft, setNameDraft] = useState(sandbox.name)
  const [labelsDraft, setLabelsDraft] = useState(labelsToComma(sandbox.labels))
  const [nameTouched, setNameTouched] = useState(false)
  const [autoStopNever, setAutoStopNever] = useState(sandbox.auto_stop_interval === 0)
  const [autoStopMinutes, setAutoStopMinutes] = useState(
    sandbox.auto_stop_interval === 0 ? "60" : String(sandbox.auto_stop_interval),
  )
  const [autoDeleteEnabled, setAutoDeleteEnabled] = useState(sandbox.auto_delete_interval !== -1)
  const [autoDeleteDays, setAutoDeleteDays] = useState(
    sandbox.auto_delete_interval === -1
      ? "7"
      : String(Math.round(sandbox.auto_delete_interval / (24 * 60))),
  )

  const tierAllowsNever = usage?.limits.max_sandbox_duration_seconds === 0
  const maxAutoStopMinutes =
    usage && usage.limits.max_sandbox_duration_seconds > 0
      ? Math.floor(usage.limits.max_sandbox_duration_seconds / 60)
      : undefined

  const autoStopMinutesDisplay = useMemo(() => {
    if (autoStopNever || maxAutoStopMinutes === undefined) {
      return autoStopMinutes
    }
    const n = parseInt(autoStopMinutes, 10)
    if (Number.isNaN(n)) {
      return autoStopMinutes
    }
    if (n > maxAutoStopMinutes) {
      return String(maxAutoStopMinutes)
    }
    return autoStopMinutes
  }, [autoStopMinutes, autoStopNever, maxAutoStopMinutes])

  const nameTrimmed = nameDraft.trim()
  const nameInvalid = nameTrimmed.length > 0 && !SANDBOX_NAME_PATTERN.test(nameTrimmed)
  const showNameError = nameTouched && nameInvalid

  async function handleSaveSettings() {
    if (nameInvalid) {
      toast.error("Fix the sandbox name before saving.")
      return
    }
    const parsedLabels = parseLabels(labelsDraft)
    if (!parsedLabels.ok) {
      toast.error("Labels must be comma-separated key=value pairs, e.g. env=dev, team=core.")
      return
    }

    let stopMinutes: number
    if (autoStopNever) {
      stopMinutes = 0
    } else {
      const n = parseInt(autoStopMinutesDisplay, 10)
      if (Number.isNaN(n) || n < 1) {
        toast.error("Auto-stop must be at least 1 minute, or enable Never if your plan allows it.")
        return
      }
      stopMinutes = maxAutoStopMinutes !== undefined ? Math.min(n, maxAutoStopMinutes) : n
    }

    let autoDelete = -1
    if (autoDeleteEnabled) {
      const days = parseInt(autoDeleteDays, 10)
      if (Number.isNaN(days) || days < 1) {
        toast.error("Auto-delete must be at least 1 day, or turn it off.")
        return
      }
      autoDelete = days * 24 * 60
    }

    const body: components["schemas"]["UpdateSandboxRequest"] = {}
    if (nameTrimmed !== sandbox.name) {
      body.name = nameTrimmed
    }
    const currentLabels = (sandbox.labels ?? {}) as Record<string, string>
    if (!labelsEqual(parsedLabels.labels, currentLabels)) {
      body.labels = parsedLabels.labels
    }
    if (stopMinutes !== sandbox.auto_stop_interval) {
      body.auto_stop_interval = stopMinutes
    }
    if (autoDelete !== sandbox.auto_delete_interval) {
      body.auto_delete_interval = autoDelete
    }

    if (Object.keys(body).length === 0) {
      toast.info("No changes to save.")
      return
    }

    try {
      const updated = await updateSandbox.mutateAsync({ id: sandbox.id, body })
      setNameDraft(updated.name)
      setLabelsDraft(labelsToComma(updated.labels))
      setNameTouched(false)
      setAutoStopNever(updated.auto_stop_interval === 0)
      setAutoStopMinutes(updated.auto_stop_interval === 0 ? "60" : String(updated.auto_stop_interval))
      const ad = updated.auto_delete_interval
      setAutoDeleteEnabled(ad !== -1)
      setAutoDeleteDays(ad === -1 ? "7" : String(Math.round(ad / (24 * 60))))
      setIsEditing(false)
      toast.success("Settings saved.")
    } catch (e) {
      const message = e instanceof HttpError ? e.message : "Could not save settings."
      toast.error(message)
    }
  }

  function handleCancelEdit() {
    const d = resetSettingsDrafts(sandbox)
    setNameDraft(d.nameDraft)
    setLabelsDraft(d.labelsDraft)
    setNameTouched(d.nameTouched)
    setAutoStopNever(d.autoStopNever)
    setAutoStopMinutes(d.autoStopMinutes)
    setAutoDeleteEnabled(d.autoDeleteEnabled)
    setAutoDeleteDays(d.autoDeleteDays)
    setIsEditing(false)
  }

  const labelsView = labelsToComma(sandbox.labels).trim() ? labelsToComma(sandbox.labels) : "—"

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2
            id="sandbox-config-heading"
            className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
          >
            Configuration
          </h2>
          <HelpIcon
            content="Editable fields map to the same lifecycle settings as the API. Template and disk are fixed after create."
            link={{ href: DOC.sandboxLifecycle.keyFields, label: "Key fields" }}
            side="right"
          />
        </div>
        {!isEditing ? (
          <button
            type="button"
            onClick={() => {
              const d = resetSettingsDrafts(sandbox)
              setNameDraft(d.nameDraft)
              setLabelsDraft(d.labelsDraft)
              setNameTouched(d.nameTouched)
              setAutoStopNever(d.autoStopNever)
              setAutoStopMinutes(d.autoStopMinutes)
              setAutoDeleteEnabled(d.autoDeleteEnabled)
              setAutoDeleteDays(d.autoDeleteDays)
              setIsEditing(true)
            }}
            className="text-[10px] font-bold uppercase tracking-[2px] text-primary underline-offset-4 hover:underline"
          >
            Edit settings
          </button>
        ) : null}
      </div>
      <div className="mt-4 border border-border/30 bg-card/70 p-6">
        {!isEditing ? (
          <div className="grid gap-8 sm:grid-cols-2">
            <ConfigReadonly label="Sandbox name">
              <span className="break-words">{sandbox.name?.trim() ? sandbox.name : "—"}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Sandbox ID">
              <span className="font-mono text-xs break-all">{sandbox.id}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Labels">
              <span className="break-words font-mono text-xs">{labelsView}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Template">
              <span className="text-muted-foreground">{templateSpec}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Persist">{sandbox.persist ? "Yes" : "No"}</ConfigReadonly>
            <ConfigReadonly label="Storage">{sandbox.storage_size ?? "—"}</ConfigReadonly>
            <ConfigReadonly label="Status">
              <span className="capitalize">{sandbox.status}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Auto-stop interval">
              <span>{autoStopViewLabel(sandbox)}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Auto-delete interval">
              <span>{autoDeleteViewLabel(sandbox)}</span>
            </ConfigReadonly>
            <ConfigReadonly label="Created">{formatDateTime(sandbox.created_at)}</ConfigReadonly>
            <ConfigReadonly label="Started">{formatDateTime(sandbox.started_at)}</ConfigReadonly>
          </div>
        ) : (
          <div className="space-y-8">
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <label
                  htmlFor="detail-sandbox-name"
                  className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                >
                  Sandbox name
                </label>
                <input
                  id="detail-sandbox-name"
                  type="text"
                  autoComplete="off"
                  value={nameDraft}
                  onBlur={() => setNameTouched(true)}
                  onChange={(e) => setNameDraft(e.target.value.toLowerCase())}
                  className="mt-2 h-10 w-full border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:border-border focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p
                  className={cn(
                    "mt-1.5 text-[10px] uppercase tracking-wide",
                    showNameError ? "text-destructive" : "text-muted-foreground/80",
                  )}
                >
                  Lowercase, numbers, hyphens only. 1–55 chars.
                </p>
              </div>
              <div>
                <label
                  htmlFor="detail-sandbox-labels"
                  className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                >
                  Labels
                </label>
                <input
                  id="detail-sandbox-labels"
                  type="text"
                  autoComplete="off"
                  placeholder="env=dev, team=core"
                  value={labelsDraft}
                  onChange={(e) => setLabelsDraft(e.target.value)}
                  className="mt-2 h-10 w-full border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:border-border focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p className="mt-1.5 text-[10px] text-muted-foreground/80">
                  Comma-separated <span className="font-mono">key=value</span> pairs.
                </p>
              </div>
            </div>

            <div className="grid gap-6 border-t border-border/20 pt-8 md:grid-cols-2">
              <div className="space-y-5">
                <div>
                  <div className="flex items-center justify-between gap-4">
                    <label
                      htmlFor="detail-auto-stop"
                      className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                    >
                      Auto-stop interval
                    </label>
                    {tierAllowsNever && (
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                          Never
                        </span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={autoStopNever}
                          onClick={() => setAutoStopNever((p) => !p)}
                          className={cn(
                            "relative h-7 w-12 shrink-0 overflow-hidden rounded-full border transition-colors",
                            autoStopNever ? "border-primary bg-primary/30" : "border-border/70 bg-muted/60",
                          )}
                        >
                          <span
                            className={cn(
                              "absolute left-0 top-0.5 size-6 rounded-full shadow transition-transform",
                              autoStopNever ? "translate-x-5 bg-primary" : "translate-x-0.5 bg-foreground/40",
                            )}
                          />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      id="detail-auto-stop"
                      type="number"
                      min={1}
                      max={maxAutoStopMinutes}
                      inputMode="numeric"
                      disabled={autoStopNever}
                      value={autoStopNever ? "" : autoStopMinutesDisplay}
                      placeholder={autoStopNever ? "Never" : undefined}
                      onChange={(e) => setAutoStopMinutes(e.target.value)}
                      className="h-10 w-full min-w-0 flex-1 border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                      Minutes
                    </span>
                  </div>
                  {maxAutoStopMinutes !== undefined && (
                    <p className="mt-1.5 text-[10px] text-muted-foreground/60">
                      Max auto-stop interval: {formatMinutes(maxAutoStopMinutes)}
                    </p>
                  )}
                </div>
                <div>
                  <div className="flex items-center justify-between gap-4">
                    <label
                      htmlFor="detail-auto-delete"
                      className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                    >
                      Auto-delete interval
                    </label>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={autoDeleteEnabled}
                      onClick={() => setAutoDeleteEnabled((p) => !p)}
                      className={cn(
                        "relative h-7 w-12 shrink-0 overflow-hidden rounded-full border transition-colors",
                        autoDeleteEnabled ? "border-primary bg-primary/30" : "border-border/70 bg-muted/60",
                      )}
                    >
                      <span
                        className={cn(
                          "absolute left-0 top-0.5 size-6 rounded-full shadow transition-transform",
                          autoDeleteEnabled ? "translate-x-5 bg-primary" : "translate-x-0.5 bg-foreground/40",
                        )}
                      />
                    </button>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      id="detail-auto-delete"
                      type="number"
                      min={1}
                      inputMode="numeric"
                      disabled={!autoDeleteEnabled}
                      value={autoDeleteDays}
                      onChange={(e) => setAutoDeleteDays(e.target.value)}
                      className="h-10 w-full min-w-0 flex-1 border border-border/40 bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                      Days
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-border/20 pt-6 sm:flex-row sm:flex-wrap">
              <button
                type="button"
                onClick={() => void handleSaveSettings()}
                disabled={updateSandbox.isPending}
                className="h-11 bg-primary text-sm font-bold uppercase tracking-[2px] text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 sm:min-w-[200px] sm:px-8"
              >
                {updateSandbox.isPending ? "Saving…" : "Save Settings"}
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                disabled={updateSandbox.isPending}
                className="h-11 border border-border/40 bg-secondary px-6 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function SandboxDetailPage() {
  const { id = "" } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: sandbox, isLoading, isError, error } = useSandbox(id)
  const { data: templatesData } = useSandboxTemplates()
  const { data: usage } = useUsageOverview()
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
    return `${t.display_name} · ${t.resource_spec.cpu} CPU · ${t.resource_spec.memory} RAM`
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

  const tierTitle = usage?.tier
    ? `${formatTierDisplayName(usage.tier).toUpperCase().replace(/\s+/g, "-")} LIMITS`
    : "PLAN LIMITS"

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
              ? "Control plane settings, data-plane URLs, and lifecycle actions."
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

              <div className="ml-auto flex items-center gap-2">
                {isReady && (
                  <button
                    type="button"
                    onClick={() => void handleStop()}
                    disabled={stopSandbox.isPending}
                    className="rounded-md border border-border/40 bg-secondary px-3 py-1.5 text-xs font-semibold text-secondary-foreground transition-[transform,background-color] hover:bg-secondary/80 active:scale-[0.97] disabled:opacity-40"
                  >
                    Stop
                  </button>
                )}
                {isCreating && (
                  <span
                    role="status"
                    aria-live="polite"
                    className="text-xs text-muted-foreground"
                  >
                    Provisioning…
                  </span>
                )}
                {canStart && (
                  <button
                    type="button"
                    onClick={() => void handleStart()}
                    disabled={startSandbox.isPending}
                    className="rounded-md border border-border/40 bg-secondary px-3 py-1.5 text-xs font-semibold text-secondary-foreground transition-[transform,background-color] hover:bg-secondary/80 active:scale-[0.97] disabled:opacity-40"
                  >
                    Start
                  </button>
                )}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => void handleDelete()}
                    disabled={deleteSandbox.isPending}
                    className="rounded-md bg-destructive px-3 py-1.5 text-xs font-bold text-destructive-foreground transition-[transform,background-color] hover:bg-destructive/88 active:scale-[0.97] disabled:opacity-50"
                  >
                    {isCreating ? "Cancel" : "Delete"}
                  </button>
                )}
              </div>
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
                  <SandboxSettingsEditor key={sandbox.id} sandbox={sandbox} templateSpec={templateSpec} />

                  <div aria-labelledby="sandbox-endpoints-heading">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2
                        id="sandbox-endpoints-heading"
                        className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                      >
                        Sandbox endpoints
                      </h2>
                      <HelpIcon
                        content={SANDBOX_ENDPOINTS_HELP}
                        link={{ href: DOCS_SANDBOX_ENDPOINTS, label: "Sandbox endpoints" }}
                        side="top"
                      />
                    </div>
                    <div className="mt-4">
                      <SandboxEndpointsDetail
                        sandbox={sandbox as Sandbox}
                        webLink={webLink ?? undefined}
                        onRecreateLink={handleRecreateLink}
                        onDeleteLink={handleDeleteLink}
                      />
                    </div>
                    <p className="mt-3">
                      <Link
                        to={DOCS_SANDBOX_ENDPOINTS}
                        className="group inline-flex items-center gap-0.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
                      >
                        Sandbox endpoints overview
                        <span aria-hidden className="opacity-50 transition-transform group-hover:translate-x-0.5">→</span>
                      </Link>
                    </p>
                  </div>
                </section>
              </>
            )}
          </div>
        </div>

        <aside className="mt-10 hidden lg:mt-0 lg:block">
          <div className="border border-border/15 bg-card p-6">
            <div className="flex items-center gap-2">
              <h2 className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">{tierTitle}</h2>
              <HelpIcon
                content="CU-hours and monthly limits are explained under Usage & Limits."
                link={{ href: DOC.usageLimits.whatIsCu, label: "What is a CU?" }}
                side="left"
              />
            </div>
            {!usage ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading limits…</p>
            ) : (
              <ul className="mt-6 space-y-5">
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">Compute usage</p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {usage.compute.compute_unit_hours.toFixed(2)}{" "}
                    <span className="text-xs font-normal text-muted-foreground">CU-h</span>
                  </p>
                </li>
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">Concurrency limit</p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {usage.limits.max_concurrent_running}{" "}
                    <span className="text-xs font-normal uppercase text-muted-foreground">max</span>
                  </p>
                </li>
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">Max auto-stop interval</p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {usage.limits.max_sandbox_duration_seconds === 0
                      ? "Unlimited"
                      : formatMinutes(Math.floor(usage.limits.max_sandbox_duration_seconds / 60))}
                  </p>
                </li>
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
