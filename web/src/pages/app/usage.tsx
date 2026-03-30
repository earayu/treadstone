import { useState } from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"

import { useGrants, useComputeSessions, useUsageOverview, useUserPlan } from "@/api/usage"
import { cn } from "@/lib/utils"
import { formatSeconds, formatMinutes } from "@/lib/format-time"

const SESSION_PAGE_SIZE = 10
const SESSION_STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
] as const

function formatPeriod(start: string, end: string): string {
  try {
    const s = new Date(start)
    const e = new Date(end)
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }
    return `${s.toLocaleDateString(undefined, opts)} – ${e.toLocaleDateString(undefined, { ...opts, year: "numeric" })}`
  } catch {
    return `${start} – ${end}`
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const h = Math.floor(m / 60)
  const remM = m % 60
  if (h === 0) return `${m}m`
  return `${h}h ${remM}m`
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

export function UsagePage() {
  const { data: usage, isLoading: uLoading } = useUsageOverview()
  const { data: plan, isLoading: pLoading } = useUserPlan()
  const [sessionStatus, setSessionStatus] = useState("all")
  const [sessionPage, setSessionPage] = useState(0)
  const { data: sessionsData, isLoading: sLoading } = useComputeSessions({
    status: sessionStatus,
    limit: SESSION_PAGE_SIZE,
    offset: sessionPage * SESSION_PAGE_SIZE,
  })
  const { data: grantsData, isLoading: gLoading } = useGrants()

  const sessions = sessionsData?.items ?? []
  const sessionsTotal = sessionsData?.total ?? 0
  const sessionsTotalPages = Math.ceil(sessionsTotal / SESSION_PAGE_SIZE)
  const computeGrants = grantsData?.compute_grants ?? []
  const storageGrants = grantsData?.storage_quota_grants ?? []

  const loading = uLoading || pLoading

  const tier = usage?.tier ?? plan?.tier ?? "—"
  const maxConcurrent = usage?.limits.max_concurrent_running ?? plan?.max_concurrent_running ?? null
  const maxDurSec = usage?.limits.max_sandbox_duration_seconds ?? plan?.max_sandbox_duration_seconds ?? null
  const maxDurMin = maxDurSec != null ? Math.round(maxDurSec / 60) : null
  const periodLabel =
    usage?.billing_period != null
      ? formatPeriod(usage.billing_period.start, usage.billing_period.end)
      : "—"

  const monthlyLimit = usage?.compute.monthly_limit ?? 0
  const monthlyUsed = usage?.compute.monthly_used ?? 0
  const totalRemaining = usage?.compute.total_remaining ?? 0
  const storageUsed = usage?.storage.current_used_gib
  const storageQuota = usage?.storage.total_quota_gib

  return (
    <div className="flex flex-col gap-10">
      <div className="border border-border/15 bg-card px-6 py-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
          <p className="text-sm text-foreground">
            <span className="text-[10px] font-bold uppercase tracking-[1.5px] text-muted-foreground">Current plan</span>
            {"  "}
            <span className="capitalize font-semibold text-primary">{tier}</span>
          </p>
          {(maxConcurrent != null || maxDurMin != null) && (
            <p className="text-xs text-muted-foreground">
              {maxConcurrent != null && `Max ${maxConcurrent} concurrent sandboxes`}
              {maxConcurrent != null && maxDurMin != null && " · "}
              {maxDurSec != null && `Max auto-stop interval: ${formatSeconds(maxDurSec)}`}
            </p>
          )}
          <p className="text-xs text-muted-foreground">Period: {periodLabel}</p>
        </div>
      </div>

      <div>
        <h1 className="text-4xl font-bold tracking-tight text-foreground">Usage &amp; Quotas</h1>
        <p className="mt-1 text-base text-muted-foreground">
          Compute consumption, quota grants, and plan limits for your workspace.
        </p>
      </div>

      <div className="grid grid-cols-1 border border-border/15 lg:grid-cols-3">
        <div className="border-b border-border/15 bg-card px-6 py-6 lg:border-b-0 lg:border-r">
          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
            Monthly compute
          </p>
          {loading ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="mt-3">
              <p className="text-sm font-semibold tabular-nums text-foreground">
                {monthlyUsed.toFixed(1)} / {monthlyLimit.toFixed(1)} CU-hours used
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Total remaining:{" "}
                <span className="tabular-nums text-foreground">{totalRemaining.toFixed(1)}</span>{" "}
                CU-hours
              </p>
            </div>
          )}
        </div>
        <div className="border-b border-border/15 bg-card px-6 py-6 lg:border-b-0 lg:border-r">
          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">
            Current tier
          </p>
          {loading ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold capitalize text-primary">{tier}</span>
              {!loading && (
                <span className="bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                  ACTIVE
                </span>
              )}
            </div>
          )}
        </div>
        <div className="bg-card px-6 py-6">
          <p className="text-[10px] font-bold uppercase tracking-[2px] text-muted-foreground">Storage</p>
          {loading ? (
            <p className="mt-3 text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold tabular-nums text-foreground">
                {storageUsed != null && storageQuota != null
                  ? `${storageUsed} / ${storageQuota}`
                  : "—"}
              </span>
              <span className="text-xs text-muted-foreground">GiB used</span>
            </div>
          )}
        </div>
      </div>

      <div className="border border-border/15 bg-black">
        <div className="flex items-center justify-between border-b border-border/15 bg-card px-6 py-4">
          <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
            Compute sessions
          </h3>
          <div className="flex gap-1">
            {SESSION_STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  setSessionStatus(opt.value)
                  setSessionPage(0)
                }}
                className={cn(
                  "px-3 py-1 text-[10px] font-bold uppercase tracking-wide transition-colors",
                  sessionStatus === opt.value
                    ? "bg-primary/15 text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead>
              <tr className="border-b border-border/15 bg-card">
                {(
                  [
                    ["Sandbox", "w-[22%]"],
                    ["Template", "w-[16%]"],
                    ["Duration", "w-[16%]"],
                    ["CU-hours", "w-[16%]"],
                    ["Status", "w-[14%]"],
                  ] as const
                ).map(([label, cls]) => (
                  <th
                    key={label}
                    className={cn(
                      "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                      cls,
                    )}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : sessions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    No compute sessions yet.
                  </td>
                </tr>
              ) : (
                sessions.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={cn("hover:bg-card/50", idx > 0 && "border-t border-border/5")}
                  >
                    <td className="px-6 py-4 font-mono text-xs text-foreground">{row.sandbox_id}</td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">{row.template}</td>
                    <td className="px-6 py-4 text-xs tabular-nums text-muted-foreground">
                      {formatDuration(row.duration_seconds)}
                    </td>
                    <td className="px-6 py-4 text-xs tabular-nums text-foreground">
                      {row.compute_unit_hours.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 text-xs capitalize text-foreground">{row.status}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {sessionsTotal > SESSION_PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border/15 bg-card px-6 py-3">
            <span className="text-[10px] uppercase tracking-[1px] text-muted-foreground">
              Showing {sessions.length} of {sessionsTotal} sessions
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setSessionPage((p) => Math.max(0, p - 1))}
                disabled={sessionPage === 0}
                className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
              >
                <ChevronLeft className="size-3" />
              </button>
              <button
                onClick={() => setSessionPage((p) => Math.min(sessionsTotalPages - 1, p + 1))}
                disabled={sessionPage >= sessionsTotalPages - 1}
                className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
              >
                <ChevronRight className="size-3" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="border border-border/15 bg-black">
        <div className="border-b border-border/15 bg-card px-6 py-4">
          <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
            Compute grants
          </h3>
          <p className="mt-1 text-[11px] text-muted-foreground/80">
            Compute Unit grants (original / remaining).
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px]">
            <thead>
              <tr className="border-b border-border/15 bg-card">
                {(
                  [
                    ["Grant type", "w-[22%]"],
                    ["Original (CU-h)", "w-[18%]"],
                    ["Remaining", "w-[18%]"],
                    ["Status", "w-[14%]"],
                    ["Expires", "w-[28%]"],
                  ] as const
                ).map(([label, cls]) => (
                  <th
                    key={label}
                    className={cn(
                      "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                      cls,
                    )}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {gLoading ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : computeGrants.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    No compute grants.
                  </td>
                </tr>
              ) : (
                computeGrants.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={cn("hover:bg-card/50", idx > 0 && "border-t border-border/5")}
                  >
                    <td className="px-6 py-4 text-sm capitalize text-foreground">{row.grant_type}</td>
                    <td className="px-6 py-4 text-xs tabular-nums text-foreground">
                      {row.original_amount.toFixed(1)}
                    </td>
                    <td className="px-6 py-4 text-xs tabular-nums text-foreground">
                      {row.remaining_amount.toFixed(1)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                        {row.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDateTime(row.expires_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border border-border/15 bg-black">
        <div className="border-b border-border/15 bg-card px-6 py-4">
          <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
            Storage quota grants
          </h3>
          <p className="mt-1 text-[11px] text-muted-foreground/80">
            Additional persistent storage quota (GiB).
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px]">
            <thead>
              <tr className="border-b border-border/15 bg-card">
                {(
                  [
                    ["Grant type", "w-[28%]"],
                    ["Size (GiB)", "w-[18%]"],
                    ["Status", "w-[14%]"],
                    ["Expires", "w-[40%]"],
                  ] as const
                ).map(([label, cls]) => (
                  <th
                    key={label}
                    className={cn(
                      "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                      cls,
                    )}
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {gLoading ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : storageGrants.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-muted-foreground">
                    No storage quota grants.
                  </td>
                </tr>
              ) : (
                storageGrants.map((row, idx) => (
                  <tr
                    key={row.id}
                    className={cn("hover:bg-card/50", idx > 0 && "border-t border-border/5")}
                  >
                    <td className="px-6 py-4 text-sm capitalize text-foreground">{row.grant_type}</td>
                    <td className="px-6 py-4 text-xs tabular-nums text-foreground">{row.size_gib}</td>
                    <td className="px-6 py-4">
                      <span className="bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                        {row.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDateTime(row.expires_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
