import { useState, useCallback } from "react"
import { Copy, ChevronLeft, ChevronRight } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useAuditEvents, useAuditFilterOptions, type AuditEvent } from "@/api/audit"

const PAGE_SIZE = 50

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return iso
  }
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  placeholder,
  width,
}: {
  label: string
  value: string
  options: string[]
  onChange: (v: string) => void
  placeholder: string
  width: string
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-medium text-muted-foreground">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "h-8 rounded-sm border border-border/40 bg-background px-2 text-[10px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring",
          !value && "text-muted-foreground/40",
          width,
        )}
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  )
}

function FilterBar({
  filters,
  onChange,
  onApply,
  onReset,
}: {
  filters: FilterState
  onChange: (patch: Partial<FilterState>) => void
  onApply: () => void
  onReset: () => void
}) {
  const { data: filterOptions } = useAuditFilterOptions()

  return (
    <div className="rounded border border-border/20 bg-card p-5">
      <p className="mb-3 text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
        FILTERS
      </p>
      <div className="flex flex-wrap gap-4">
        <FilterSelect
          label="Action"
          value={filters.action}
          options={filterOptions?.actions ?? []}
          onChange={(v) => onChange({ action: v })}
          placeholder="All actions"
          width="w-[200px]"
        />
        <FilterSelect
          label="Target Type"
          value={filters.target_type}
          options={filterOptions?.target_types ?? []}
          onChange={(v) => onChange({ target_type: v })}
          placeholder="All types"
          width="w-[180px]"
        />
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">Target ID</label>
          <input
            type="text"
            value={filters.target_id}
            onChange={(e) => onChange({ target_id: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && onApply()}
            placeholder="resource ID"
            className="h-8 w-[160px] rounded-sm border border-border/40 bg-background px-2 text-[10px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-muted-foreground">Actor Email</label>
          <input
            type="email"
            value={filters.actor_email}
            onChange={(e) => onChange({ actor_email: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && onApply()}
            placeholder="user@example.com"
            className="h-8 w-[200px] rounded-sm border border-border/40 bg-background px-2 text-[10px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <FilterSelect
          label="Result"
          value={filters.result}
          options={filterOptions?.results ?? []}
          onChange={(v) => onChange({ result: v })}
          placeholder="All results"
          width="w-[140px]"
        />
      </div>
      <div className="mt-4 flex gap-2">
        <button
          onClick={onApply}
          className="rounded-sm bg-primary px-5 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Apply Filters
        </button>
        <button
          onClick={onReset}
          className="rounded-sm border border-border/40 px-5 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent"
        >
          Reset
        </button>
      </div>
    </div>
  )
}

function EventRow({ event }: { event: AuditEvent }) {
  const copyRequestId = useCallback(() => {
    if (event.request_id) {
      navigator.clipboard.writeText(event.request_id).then(
        () => toast.success("Request ID copied"),
        () => toast.error("Failed to copy"),
      )
    }
  }, [event.request_id])

  return (
    <tr className="border-b border-border/10 transition-colors hover:bg-card/50">
      <td className="px-4 py-3 text-xs tabular-nums text-muted-foreground">
        {formatTimestamp(event.created_at)}
      </td>
      <td className="px-4 py-3 text-xs font-medium text-primary">{event.action}</td>
      <td className="px-4 py-3 font-mono text-xs text-foreground">{event.target_id ?? "—"}</td>
      <td className="px-4 py-3 font-mono text-xs text-foreground">
        {event.actor_user_id ?? event.actor_api_key_id ?? "—"}
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            "text-xs font-medium",
            event.result === "success" ? "text-primary" : "text-destructive",
          )}
        >
          {event.result}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {event.credential_type ?? "—"}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-muted-foreground">
            {event.request_id ?? "—"}
          </span>
          {event.request_id && (
            <button
              onClick={copyRequestId}
              className="text-muted-foreground/40 transition-colors hover:text-foreground"
            >
              <Copy className="size-3" />
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

interface FilterState {
  action: string
  target_type: string
  target_id: string
  actor_email: string
  result: string
}

const EMPTY_FILTERS: FilterState = {
  action: "",
  target_type: "",
  target_id: "",
  actor_email: "",
  result: "",
}

export function AuditEventsPage() {
  const [draft, setDraft] = useState<FilterState>(EMPTY_FILTERS)
  const [applied, setApplied] = useState<FilterState>(EMPTY_FILTERS)
  const [page, setPage] = useState(0)

  const queryParams = {
    action: applied.action || undefined,
    target_type: applied.target_type || undefined,
    target_id: applied.target_id || undefined,
    actor_email: applied.actor_email || undefined,
    result: applied.result || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  }

  const { data, isLoading, isError, refetch } = useAuditEvents(queryParams)
  const events = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleApply = () => {
    setApplied({ ...draft })
    setPage(0)
  }

  const handleReset = () => {
    setDraft(EMPTY_FILTERS)
    setApplied(EMPTY_FILTERS)
    setPage(0)
  }

  const columns = [
    { label: "TIMESTAMP", className: "w-[16%]" },
    { label: "ACTION", className: "w-[16%]" },
    { label: "TARGET", className: "w-[14%]" },
    { label: "ACTOR", className: "w-[14%]" },
    { label: "RESULT", className: "w-[8%]" },
    { label: "CRED TYPE", className: "w-[10%]" },
    { label: "REQUEST ID", className: "w-[22%]" },
  ] as const

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">Audit Events</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Browse structured audit events with filtering and incident investigation.
        </p>
      </div>

      <FilterBar
        filters={draft}
        onChange={(patch) => setDraft((prev) => ({ ...prev, ...patch }))}
        onApply={handleApply}
        onReset={handleReset}
      />

      <div className="border border-border/20 bg-black rounded">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-border/20 bg-card">
                {columns.map((col) => (
                  <th
                    key={col.label}
                    className={cn(
                      "px-4 py-3 text-left text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground",
                      col.className,
                    )}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    Loading…
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-destructive">
                    Failed to load audit events.{" "}
                    <button onClick={() => refetch()} className="underline hover:text-destructive/80">
                      Retry
                    </button>
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    No audit events found.
                  </td>
                </tr>
              ) : (
                events.map((event) => <EventRow key={event.id} event={event} />)
              )}
            </tbody>
          </table>
        </div>

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border/15 bg-card px-5 py-3">
            <span className="text-[10px] uppercase tracking-[1px] text-muted-foreground">
              Showing {events.length} of {total} events
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
        )}
      </div>
    </div>
  )
}
