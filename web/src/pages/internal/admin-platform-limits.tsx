import { useMemo, useState } from "react"
import { toast } from "sonner"
import { RefreshCw, SlidersHorizontal } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  usePlatformLimitsConfig,
  useUpdatePlatformLimits,
  type PlatformLimitsFormState,
  type PlatformLimitsResponse,
} from "@/api/admin"
import type { components } from "@/api/schema"

type Config = components["schemas"]["PlatformLimitsConfig"]

function configToForm(c: Config): PlatformLimitsFormState {
  const s = (n: number | null | undefined) => (n != null ? String(n) : "")
  return {
    max_registered_users: s(c.max_registered_users),
    max_total_sandboxes: s(c.max_total_sandboxes),
    max_total_storage_gib: s(c.max_total_storage_gib),
    max_waitlist_applications: s(c.max_waitlist_applications),
  }
}

function parseLimitField(raw: string): number | null {
  const t = raw.trim()
  if (t === "") return null
  const n = Number.parseInt(t, 10)
  if (Number.isNaN(n) || n < 0) return null
  return n
}

function buildPatch(
  initial: PlatformLimitsFormState,
  draft: PlatformLimitsFormState,
): components["schemas"]["UpdatePlatformLimitsRequest"] | null {
  const out: components["schemas"]["UpdatePlatformLimitsRequest"] = {}
  const keys = [
    "max_registered_users",
    "max_total_sandboxes",
    "max_total_storage_gib",
    "max_waitlist_applications",
  ] as const
  for (const k of keys) {
    const a = parseLimitField(String(initial[k]))
    const b = parseLimitField(String(draft[k]))
    if (a !== b) {
      out[k] = b
    }
  }
  return Object.keys(out).length > 0 ? out : null
}

export function AdminPlatformLimitsPage() {
  const { data, isLoading, isError, refetch, isFetching, dataUpdatedAt } = usePlatformLimitsConfig()

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null

  return (
    <div className="flex flex-col gap-8 p-8">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="size-5 text-muted-foreground" />
            <h1 className="text-lg font-semibold text-foreground">Platform limits</h1>
          </div>
          <p className="max-w-2xl text-xs text-muted-foreground">
            Best-effort global caps (registered users, sandboxes, persistent storage GiB, waitlist
            submissions). Leave a field empty for no limit. Changes apply on save; enforcement uses
            periodic refresh across API pods.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {lastUpdated && (
            <span className="text-[10px] text-muted-foreground">Loaded {lastUpdated}</span>
          )}
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded border border-border/30 bg-card px-3 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-card/80 disabled:opacity-50"
          >
            <RefreshCw className={cn("size-3", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {isError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-xs text-destructive">
          Failed to load platform limits. Ensure you are signed in as an admin.
        </div>
      )}

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : data ? (
        <>
          <UsagePanel data={data} />
          <PlatformLimitsEditor key={data.refreshed_at} data={data} />
        </>
      ) : null}
    </div>
  )
}

function UsagePanel({ data }: { data: PlatformLimitsResponse }) {
  return (
    <div className="rounded-lg border border-border/20 bg-card/50 p-5">
      <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Current usage (live)
      </h2>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <UsagePill label="Registered users" value={data.usage.registered_users} />
        <UsagePill label="Sandboxes" value={data.usage.total_sandboxes} />
        <UsagePill label="Storage (GiB)" value={data.usage.total_storage_gib} />
        <UsagePill label="Waitlist apps" value={data.usage.waitlist_applications} />
      </div>
      <p className="mt-3 text-[10px] text-muted-foreground">
        Refreshed at {new Date(data.refreshed_at).toLocaleString()}
      </p>
    </div>
  )
}

function PlatformLimitsEditor({ data }: { data: PlatformLimitsResponse }) {
  const updateLimits = useUpdatePlatformLimits()
  const [form, setForm] = useState(() => configToForm(data.config))
  const [initialForm] = useState(() => configToForm(data.config))

  const dirty = useMemo(() => buildPatch(initialForm, form) !== null, [initialForm, form])

  const handleSave = () => {
    const patch = buildPatch(initialForm, form)
    if (!patch) {
      toast.message("No changes to save.")
      return
    }
    updateLimits.mutate(patch, {
      onSuccess: () => {
        toast.success("Platform limits updated.")
      },
      onError: (e: Error) => toast.error(e.message),
    })
  }

  const handleReset = () => {
    setForm({ ...initialForm })
  }

  return (
    <div className="rounded-lg border border-border/20 bg-card p-5">
      <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        Limits
      </h2>
      <div className="grid max-w-2xl grid-cols-1 gap-4 md:grid-cols-2">
        <LimitField
          label="Max registered users"
          hint="Empty = unlimited"
          value={form.max_registered_users}
          onChange={(v) => setForm((f) => ({ ...f, max_registered_users: v }))}
        />
        <LimitField
          label="Max total sandboxes"
          hint="Non-deleted sandboxes"
          value={form.max_total_sandboxes}
          onChange={(v) => setForm((f) => ({ ...f, max_total_sandboxes: v }))}
        />
        <LimitField
          label="Max total storage (GiB)"
          hint="Persistent volumes only"
          value={form.max_total_storage_gib}
          onChange={(v) => setForm((f) => ({ ...f, max_total_storage_gib: v }))}
        />
        <LimitField
          label="Max waitlist applications"
          hint="Empty = unlimited"
          value={form.max_waitlist_applications}
          onChange={(v) => setForm((f) => ({ ...f, max_waitlist_applications: v }))}
        />
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || updateLimits.isPending}
          className="rounded bg-primary px-4 py-2 text-xs font-semibold uppercase tracking-wider text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {updateLimits.isPending ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={handleReset}
          disabled={!dirty || updateLimits.isPending}
          className="rounded border border-border/40 px-4 py-2 text-xs text-muted-foreground transition-colors hover:bg-muted/30 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Reset
        </button>
      </div>
    </div>
  )
}

function UsagePill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-border/30 bg-background px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums text-foreground">{value}</div>
    </div>
  )
}

function LimitField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string
  hint: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium text-foreground">{label}</span>
      <input
        type="text"
        inputMode="numeric"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Unlimited"
        className="h-[38px] rounded-sm border border-border/40 bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <span className="text-[10px] text-muted-foreground">{hint}</span>
    </label>
  )
}
