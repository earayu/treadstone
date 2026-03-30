import { RefreshCw, Users, Box, Cpu, HardDrive, Activity } from "lucide-react"
import { cn } from "@/lib/utils"
import { usePlatformStats } from "@/api/admin"

const STATUS_LABELS: Record<string, string> = {
  creating: "Creating",
  ready: "Ready",
  stopped: "Stopped",
  error: "Error",
  deleting: "Deleting",
  deleted: "Deleted",
}

const STATUS_COLORS: Record<string, string> = {
  creating: "text-blue-400",
  ready: "text-emerald-400",
  stopped: "text-muted-foreground",
  error: "text-destructive",
  deleting: "text-amber-400",
  deleted: "text-muted-foreground/60",
}

const STATUS_DOT_COLORS: Record<string, string> = {
  creating: "bg-blue-400",
  ready: "bg-emerald-400",
  stopped: "bg-muted-foreground",
  error: "bg-destructive",
  deleting: "bg-amber-400",
  deleted: "bg-muted-foreground/60",
}

function StatusDot({ status }: { status: string }) {
  return <span className={cn("inline-block size-2 rounded-full", STATUS_DOT_COLORS[status] ?? "bg-muted-foreground")} />
}

interface KpiCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  sub?: string
}

function KpiCard({ icon, label, value, sub }: KpiCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border/20 bg-card p-5">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-widest">{label}</span>
      </div>
      <div className="text-3xl font-semibold tabular-nums text-foreground">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  )
}

export function AdminOverviewPage() {
  const { data, isLoading, isError, dataUpdatedAt, refetch, isFetching } = usePlatformStats()

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null

  const total = data?.sandboxes.status_breakdown.reduce((s, r) => s + r.count, 0) ?? 0

  return (
    <div className="flex flex-col gap-8 p-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-foreground">Platform Overview</h1>
          <p className="text-xs text-muted-foreground">Real-time operational metrics across all tenants.</p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-[10px] text-muted-foreground">
              Last updated {lastUpdated}
            </span>
          )}
          <button
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
          Failed to load platform stats. Check server connectivity.
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          icon={<Users className="size-3.5" />}
          label="Total Users"
          value={isLoading ? "—" : (data?.users.total ?? 0).toLocaleString()}
          sub={isLoading ? undefined : `${data?.users.active ?? 0} active · ${data?.users.admin_count ?? 0} admin`}
        />
        <KpiCard
          icon={<Box className="size-3.5" />}
          label="Total Sandboxes"
          value={isLoading ? "—" : (data?.sandboxes.total_created ?? 0).toLocaleString()}
          sub="All time, all statuses"
        />
        <KpiCard
          icon={<Activity className="size-3.5" />}
          label="Running Now"
          value={isLoading ? "—" : (data?.sandboxes.currently_running ?? 0).toLocaleString()}
          sub="Status: ready"
        />
        <KpiCard
          icon={<HardDrive className="size-3.5" />}
          label="Allocated Storage"
          value={isLoading ? "—" : `${(data?.storage.total_allocated_gib ?? 0).toFixed(1)} GiB`}
          sub={
            isLoading
              ? undefined
              : `${(data?.storage.total_consumed_gib_hours ?? 0).toFixed(2)} GiB·h consumed`
          }
        />
      </div>

      {/* Compute usage */}
      <div className="rounded-lg border border-border/20 bg-card p-5">
        <div className="mb-4 flex items-center gap-2 text-muted-foreground">
          <Cpu className="size-3.5" />
          <span className="text-[10px] font-semibold uppercase tracking-widest">Compute Usage — Current Billing Period</span>
        </div>
        <div className="flex items-end gap-2">
          <span className="text-3xl font-semibold tabular-nums text-foreground">
            {isLoading ? "—" : (data?.compute.total_cu_hours_this_period ?? 0).toFixed(4)}
          </span>
          <span className="mb-1 text-sm text-muted-foreground">CU-hours consumed (platform total)</span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Sum of <code className="rounded bg-muted px-1 py-0.5 text-[10px]">compute_units_monthly_used</code> across all
          active user plans for the current billing period.
        </p>
      </div>

      {/* Sandbox status breakdown */}
      <div className="rounded-lg border border-border/20 bg-card">
        <div className="border-b border-border/20 px-5 py-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Box className="size-3.5" />
            <span className="text-[10px] font-semibold uppercase tracking-widest">Sandbox Status Breakdown</span>
          </div>
        </div>

        {isLoading ? (
          <div className="px-5 py-8 text-center text-xs text-muted-foreground">Loading…</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/15">
                <th className="px-5 py-2.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Status
                </th>
                <th className="px-5 py-2.5 text-right text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Count
                </th>
                <th className="px-5 py-2.5 text-right text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Share
                </th>
              </tr>
            </thead>
            <tbody>
              {(data?.sandboxes.status_breakdown ?? [])
                .slice()
                .sort((a, b) => b.count - a.count)
                .map((row) => {
                  const pct = total > 0 ? ((row.count / total) * 100).toFixed(1) : "0.0"
                  return (
                    <tr
                      key={row.status}
                      className="border-b border-border/15 transition-colors last:border-0 hover:bg-card/50"
                    >
                      <td className="px-5 py-3">
                        <span
                          className={cn(
                            "inline-flex items-center gap-2 text-xs font-medium",
                            STATUS_COLORS[row.status] ?? "text-foreground",
                          )}
                        >
                          <StatusDot status={row.status} />
                          {STATUS_LABELS[row.status] ?? row.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-right text-xs tabular-nums text-foreground">
                        {row.count.toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-right text-xs tabular-nums text-muted-foreground">{pct}%</td>
                    </tr>
                  )
                })}
              {(data?.sandboxes.status_breakdown ?? []).length === 0 && (
                <tr>
                  <td colSpan={3} className="px-5 py-6 text-center text-xs text-muted-foreground">
                    No sandbox data available.
                  </td>
                </tr>
              )}
            </tbody>
            {total > 0 && (
              <tfoot>
                <tr className="border-t border-border/20 bg-muted/20">
                  <td className="px-5 py-2.5 text-xs font-semibold text-muted-foreground">Total</td>
                  <td className="px-5 py-2.5 text-right text-xs font-semibold tabular-nums text-foreground">
                    {total.toLocaleString()}
                  </td>
                  <td className="px-5 py-2.5 text-right text-xs text-muted-foreground">100%</td>
                </tr>
              </tfoot>
            )}
          </table>
        )}
      </div>
    </div>
  )
}
