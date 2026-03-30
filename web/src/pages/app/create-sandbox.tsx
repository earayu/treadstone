import { useEffect, useMemo, useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"

import { useCreateSandbox } from "@/api/sandboxes"
import { useSandboxTemplates, type SandboxTemplate } from "@/api/templates"
import { useUsageOverview } from "@/api/usage"
import { useCurrentUser } from "@/hooks/use-auth"
import { HttpError } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { formatSeconds, formatMinutes } from "@/lib/format-time"

const SANDBOX_NAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?$/

const STORAGE_OPTIONS = ["5Gi", "10Gi", "20Gi"] as const

function formatVcpuDisplay(cpu: string): string {
  const trimmed = cpu.trim()
  if (trimmed.endsWith("m")) {
    const m = parseInt(trimmed.slice(0, -1), 10)
    if (Number.isNaN(m)) return trimmed
    const v = m / 1000
    return (Math.round(v * 10) / 10).toFixed(1)
  }
  const n = parseFloat(trimmed)
  if (Number.isNaN(n)) return trimmed
  return (Math.round(n * 10) / 10).toFixed(1)
}

function templateSizeLabel(t: SandboxTemplate): string {
  const v = formatVcpuDisplay(t.resource_spec.cpu)
  return `${v}v`
}

function templateShortLabel(displayName: string): string {
  const parts = displayName.trim().split(/\s+/)
  return (parts[parts.length - 1] ?? displayName).toUpperCase()
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

export function CreateSandboxPage() {
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const { data: templatesData, isLoading: templatesLoading } = useSandboxTemplates()
  const { data: usage, isLoading: usageLoading } = useUsageOverview()
  const createMutation = useCreateSandbox()
  const isUnverified = user && !user.is_verified

  const visibleTemplates = useMemo(() => {
    const items = templatesData?.items ?? []
    const allowed = usage?.limits.allowed_templates
    if (!allowed?.length) return items
    const allow = new Set(allowed)
    return items.filter((t) => allow.has(t.name))
  }, [templatesData, usage])

  const defaultTemplate = useMemo(() => {
    if (visibleTemplates.length === 0) return ""
    const tiny = visibleTemplates.find((t) => t.name === "aio-sandbox-tiny")
    return tiny ? tiny.name : visibleTemplates[0].name
  }, [visibleTemplates])

  const [selectedTemplate, setSelectedTemplate] = useState<string>("")
  const [name, setName] = useState("")
  const [labelsRaw, setLabelsRaw] = useState("")
  const [autoStopMinutes, setAutoStopMinutes] = useState("60")
  const [autoDeleteEnabled, setAutoDeleteEnabled] = useState(false)
  const [autoDeleteMinutes, setAutoDeleteMinutes] = useState("10080")
  const [persist, setPersist] = useState(false)
  const [storageSize, setStorageSize] = useState<"5Gi" | "10Gi" | "20Gi">("5Gi")
  const [nameTouched, setNameTouched] = useState(false)

  const activeTemplate = selectedTemplate || defaultTemplate

  const maxAutoStopMinutes = usage
    ? Math.floor(usage.limits.max_sandbox_duration_seconds / 60)
    : undefined

  useEffect(() => {
    if (maxAutoStopMinutes === undefined) {
      return
    }

    const currentMinutes = parseInt(autoStopMinutes, 10)
    if (Number.isNaN(currentMinutes) || currentMinutes <= maxAutoStopMinutes) {
      return
    }

    setAutoStopMinutes(String(maxAutoStopMinutes))
  }, [autoStopMinutes, maxAutoStopMinutes])

  const nameTrimmed = name.trim()
  const nameInvalid =
    nameTrimmed.length > 0 && !SANDBOX_NAME_PATTERN.test(nameTrimmed)
  const showNameError = nameTouched && nameInvalid

  const tierTitle = usage?.tier
    ? `${usage.tier.toUpperCase().replace(/\s+/g, "-")}-TIER ALLOCATION`
    : "TIER ALLOCATION"

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()

    if (!activeTemplate) {
      toast.error("Select a template.")
      return
    }

    if (nameInvalid) {
      toast.error("Fix the sandbox name before continuing.")
      return
    }

    const parsedLabels = parseLabels(labelsRaw)
    if (!parsedLabels.ok) {
      toast.error('Labels must be comma-separated key=value pairs, e.g. env=dev,team=core.')
      return
    }

    const stop = parseInt(autoStopMinutes, 10)
    if (Number.isNaN(stop) || stop < 1) {
      toast.error("Auto-stop must be at least 1 minute.")
      return
    }
    if (maxAutoStopMinutes !== undefined && stop > maxAutoStopMinutes) {
      toast.error(`Auto-stop interval cannot exceed plan limit (${maxAutoStopMinutes} min).`)
      return
    }

    let autoDelete = -1
    if (autoDeleteEnabled) {
      const del = parseInt(autoDeleteMinutes, 10)
      if (Number.isNaN(del) || del < 1) {
        toast.error("Auto-delete must be at least 1 minute, or turn it off.")
        return
      }
      autoDelete = del
    }

    try {
      await createMutation.mutateAsync({
        template: activeTemplate,
        name: nameTrimmed.length > 0 ? nameTrimmed : null,
        labels: parsedLabels.labels,
        auto_stop_interval: stop,
        auto_delete_interval: autoDelete,
        persist,
        storage_size: persist ? storageSize : null,
      })
      toast.success("Sandbox created.")
      navigate("/app")
    } catch (err) {
      const message =
        err instanceof HttpError ? err.message : "Could not create sandbox."
      toast.error(message)
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
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Create Sandbox
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Configure and deploy a new sandbox environment.
          </p>

          {isUnverified && (
            <div className="mt-4 border-l-4 border-amber-500 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
              Please verify your email before creating sandboxes. Check your inbox for a verification link.
            </div>
          )}

          <form className="mt-8 space-y-8" onSubmit={handleSubmit} noValidate>
            <section>
              <h2 className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
                Template
              </h2>
              {templatesLoading || usageLoading ? (
                <p className="mt-3 text-sm text-muted-foreground">Loading templates…</p>
              ) : visibleTemplates.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">
                  No templates available for your plan.
                </p>
              ) : (
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
                  {visibleTemplates.map((t) => {
                    const selected = t.name === activeTemplate
                    return (
                      <button
                        key={t.name}
                        type="button"
                        onClick={() => setSelectedTemplate(t.name)}
                        className={cn(
                          "flex flex-col items-start border bg-card p-4 text-left transition-colors",
                          "hover:border-border focus:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                          selected
                            ? "border-primary ring-1 ring-primary"
                            : "border-border/40",
                        )}
                      >
                        <span className="text-xs font-bold text-foreground">
                          {templateShortLabel(t.display_name)}
                        </span>
                        <span className="mt-1 text-[11px] font-medium text-primary">
                          {templateSizeLabel(t)}
                        </span>
                        <span className="mt-2 line-clamp-2 text-[10px] leading-snug text-muted-foreground">
                          {t.description || `${t.resource_spec.cpu} CPU · ${t.resource_spec.memory}`}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </section>

            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <label
                  htmlFor="sandbox-name"
                  className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                >
                  Sandbox name (optional)
                </label>
                <input
                  id="sandbox-name"
                  type="text"
                  autoComplete="off"
                  placeholder="my-sandbox"
                  value={name}
                  onBlur={() => setNameTouched(true)}
                  onChange={(e) => setName(e.target.value.toLowerCase())}
                  className="mt-2 h-10 w-full border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:border-border focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p
                  className={cn(
                    "mt-1.5 text-[10px] uppercase tracking-wide",
                    showNameError ? "text-destructive" : "text-muted-foreground/80",
                  )}
                >
                  Lowercase, numbers, hyphens only. 1-55 chars.
                </p>
              </div>
              <div>
                <label
                  htmlFor="sandbox-labels"
                  className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                >
                  Labels
                </label>
                <input
                  id="sandbox-labels"
                  type="text"
                  autoComplete="off"
                  placeholder="env=dev, team=core"
                  value={labelsRaw}
                  onChange={(e) => setLabelsRaw(e.target.value)}
                  className="mt-2 h-10 w-full border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:border-border focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <p className="mt-1.5 text-[10px] text-muted-foreground/80">
                  Comma-separated <span className="font-mono">key=value</span> pairs.
                </p>
              </div>
            </div>

            <div className="grid gap-6 border border-border/30 bg-card/70 p-6 md:grid-cols-2">
              <div className="space-y-5">
                <div>
                  <label
                    htmlFor="auto-stop"
                    className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                  >
                    Auto-stop interval
                  </label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      id="auto-stop"
                      type="number"
                      min={1}
                      max={maxAutoStopMinutes}
                      inputMode="numeric"
                      value={autoStopMinutes}
                      onChange={(e) => setAutoStopMinutes(e.target.value)}
                      className="h-10 w-full min-w-0 flex-1 border border-border/40 bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
                      htmlFor="auto-delete"
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
                        autoDeleteEnabled
                          ? "border-primary bg-primary/30"
                          : "border-border/70 bg-muted/60",
                      )}
                    >
                      <span
                        className={cn(
                          "absolute left-0 top-0.5 size-6 rounded-full shadow transition-transform",
                          autoDeleteEnabled
                            ? "translate-x-5 bg-primary"
                            : "translate-x-0.5 bg-foreground/40",
                        )}
                      />
                    </button>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      id="auto-delete"
                      type="number"
                      min={1}
                      inputMode="numeric"
                      disabled={!autoDeleteEnabled}
                      value={autoDeleteMinutes}
                      onChange={(e) => setAutoDeleteMinutes(e.target.value)}
                      className="h-10 w-full min-w-0 flex-1 border border-border/40 bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                    />
                    <span className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                      Minutes
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-5 border-t border-border/30 pt-5 md:border-l md:border-t-0 md:pl-6 md:pt-0">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-[10px] font-bold uppercase tracking-[2px] text-foreground/70">
                    Data persistence
                  </span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={persist}
                    onClick={() => setPersist((p) => !p)}
                    className={cn(
                      "relative h-7 w-12 shrink-0 overflow-hidden rounded-full border transition-colors",
                      persist
                        ? "border-primary bg-primary/30"
                        : "border-border/70 bg-muted/60",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute left-0 top-0.5 size-6 rounded-full shadow transition-transform",
                        persist
                          ? "translate-x-5 bg-primary"
                          : "translate-x-0.5 bg-foreground/40",
                      )}
                    />
                  </button>
                </div>
                {persist && (
                  <div>
                    <label
                      htmlFor="storage-size"
                      className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground"
                    >
                      Storage size
                    </label>
                    <select
                      id="storage-size"
                      value={storageSize}
                      onChange={(e) =>
                        setStorageSize(e.target.value as "5Gi" | "10Gi" | "20Gi")
                      }
                      className="mt-2 h-10 w-full border border-border/40 bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {STORAGE_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={
                createMutation.isPending ||
                !activeTemplate ||
                visibleTemplates.length === 0 ||
                !!isUnverified
              }
              className="h-12 w-full bg-primary text-sm font-bold uppercase tracking-[2px] text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating…" : "Create sandbox"}
            </button>
          </form>
        </div>

        <aside className="mt-10 lg:mt-0">
          <div className="border border-border/15 bg-card p-6">
            <h2 className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
              {tierTitle}
            </h2>
            {usageLoading || !usage ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading limits…</p>
            ) : (
              <ul className="mt-6 space-y-5">
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
                    Compute usage
                  </p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {usage.compute.compute_unit_hours.toFixed(2)}{" "}
                    <span className="text-xs font-normal text-muted-foreground">
                      CU-h
                    </span>
                  </p>
                </li>
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
                    Concurrency limit
                  </p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {usage.limits.max_concurrent_running}{" "}
                    <span className="text-xs font-normal uppercase text-muted-foreground">
                      max
                    </span>
                  </p>
                </li>
                <li>
                  <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
                    Max auto-stop interval
                  </p>
                  <p className="mt-1 text-lg font-bold text-foreground">
                    {formatSeconds(usage.limits.max_sandbox_duration_seconds)}
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
