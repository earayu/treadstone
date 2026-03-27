import { useState, useMemo } from "react"
import { Link } from "react-router"
import { Plus, Search, ChevronLeft, ChevronRight } from "lucide-react"
import { useSandboxes, type Sandbox } from "@/api/sandboxes"
import { useUsageOverview } from "@/api/usage"
import { useCreditGrants } from "@/api/usage"
import { cn } from "@/lib/utils"

const PAGE_SIZE = 4

function formatRelativeTime(dateStr: string): string {
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

function StatusDot({ status }: { status: string }) {
  const isRunning = status === "ready" || status === "creating"
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-block size-1.5 rounded-full",
          isRunning ? "bg-primary" : "bg-muted-foreground/60",
        )}
      />
      <span
        className={cn(
          "text-xs font-medium capitalize",
          isRunning ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {status === "ready" ? "Running" : status}
      </span>
    </div>
  )
}

function InlineMetrics() {
  const { data: usage } = useUsageOverview()
  const { data: grants } = useCreditGrants()

  const computeRemaining = usage
    ? (usage.compute.monthly_limit - usage.compute.monthly_used).toFixed(1)
    : "—"
  const tier = usage?.tier ?? "—"

  const welcomeBonus = useMemo(() => {
    if (!grants?.items) return "—"
    const bonus = grants.items.find(
      (g) => g.grant_type === "welcome_bonus" && g.status === "active",
    )
    return bonus ? bonus.remaining_amount.toFixed(1) : "0"
  }, [grants])

  return (
    <div className="grid grid-cols-3 border border-border/15">
      <div className="border-r border-border/15 bg-card px-6 py-6">
        <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
          Compute Remaining
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-foreground">{computeRemaining}</span>
          <span className="text-xs text-muted-foreground">vCPU-hours</span>
        </div>
      </div>
      <div className="border-r border-border/15 bg-card px-6 py-6">
        <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
          Current Tier
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold capitalize text-primary">{tier}</span>
          {usage && (
            <span className="bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
              ACTIVE
            </span>
          )}
        </div>
      </div>
      <div className="bg-card px-6 py-6">
        <p className="text-[10px] uppercase tracking-[2px] text-muted-foreground">
          Welcome Bonus Credit
        </p>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-2xl font-bold text-foreground">{welcomeBonus}</span>
          <span className="text-xs text-muted-foreground">vCPU-hours remaining</span>
        </div>
      </div>
    </div>
  )
}

const TABLE_COLUMNS = [
  { key: "id", label: "Sandbox ID", className: "w-[20%]" },
  { key: "status", label: "Status", className: "w-[14%]" },
  { key: "template", label: "Template", className: "w-[16%]" },
  { key: "created_at", label: "Created At", className: "w-[18%]" },
  { key: "web_url", label: "Web URL", className: "w-[32%]" },
] as const

function SandboxTable({ sandboxes }: { sandboxes: Sandbox[] }) {
  const [filter, setFilter] = useState("")
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    if (!filter) return sandboxes
    const q = filter.toLowerCase()
    return sandboxes.filter(
      (s) => s.id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
    )
  }, [sandboxes, filter])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const pageItems = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  return (
    <div className="border border-border/15 bg-black">
      <div className="flex items-center justify-between border-b border-border/15 bg-card px-6 py-4">
        <h3 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
          Recent Sandboxes
        </h3>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground/60" />
          <input
            type="text"
            placeholder="Filter IDs..."
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setPage(0)
            }}
            className="h-8 w-48 bg-background pl-7 pr-3 text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      <table className="w-full">
        <thead>
          <tr className="border-b border-border/15 bg-card">
            {TABLE_COLUMNS.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-6 py-3 text-left text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground",
                  col.className,
                )}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageItems.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-6 py-12 text-center text-sm text-muted-foreground">
                {filter ? "No sandboxes match your filter." : "No sandboxes yet."}
              </td>
            </tr>
          ) : (
            pageItems.map((sandbox, idx) => (
              <tr
                key={sandbox.id}
                className={cn(
                  "transition-colors hover:bg-card/50",
                  idx > 0 && "border-t border-border/5",
                )}
              >
                <td className="px-6 py-4">
                  <Link
                    to={`/app/sandboxes/${sandbox.id}`}
                    className="font-mono text-xs text-foreground hover:text-primary"
                  >
                    {sandbox.name || sandbox.id}
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <StatusDot status={sandbox.status} />
                </td>
                <td className="px-6 py-4 text-xs text-muted-foreground">
                  {sandbox.template}
                </td>
                <td className="px-6 py-4 text-xs text-muted-foreground">
                  {formatRelativeTime(sandbox.created_at)}
                </td>
                <td className="px-6 py-4">
                  {sandbox.urls?.web ? (
                    <a
                      href={sandbox.urls.web}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs text-primary/80 hover:text-primary"
                    >
                      {new URL(sandbox.urls.web).hostname}
                    </a>
                  ) : sandbox.urls?.proxy ? (
                    <a
                      href={sandbox.urls.proxy}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs text-primary/80 hover:text-primary"
                    >
                      {sandbox.name ?? sandbox.id}.tread.zone
                    </a>
                  ) : (
                    <span className="text-xs text-muted-foreground/40">—</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className="flex items-center justify-between border-t border-border/15 bg-card px-6 py-3">
        <span className="text-[10px] uppercase tracking-[1px] text-muted-foreground">
          Showing {pageItems.length} of {filtered.length} sandboxes
        </span>
        <div className="flex gap-1">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
          >
            <ChevronLeft className="size-3" />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
          >
            <ChevronRight className="size-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { data: sandboxData, isLoading } = useSandboxes()
  const sandboxes = sandboxData?.items ?? []

  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-foreground">Sandboxes</h1>
          <p className="mt-1 text-base text-muted-foreground">
            Create and manage isolated sandbox environments for AI agents.
          </p>
        </div>
        <Link
          to="/app/sandboxes/new"
          className="flex items-center gap-2 bg-primary px-6 py-2.5 font-bold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Plus className="size-4" />
          Create Sandbox
        </Link>
      </div>

      <InlineMetrics />

      {isLoading ? (
        <div className="border border-border/15 bg-card px-6 py-12 text-center text-sm text-muted-foreground">
          Loading sandboxes…
        </div>
      ) : (
        <SandboxTable sandboxes={sandboxes} />
      )}
    </div>
  )
}
