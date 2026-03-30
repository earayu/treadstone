import { MessageSquareText } from "lucide-react"
import { ADMIN_FEEDBACK_PAGE_SIZE, useAdminFeedbackList } from "@/api/support"

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

export function AdminFeedbackPage() {
  const { data, isLoading, isError, isFetching, refetch } = useAdminFeedbackList(0)

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const showingAll = total <= ADMIN_FEEDBACK_PAGE_SIZE

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-foreground">Support feedback</h1>
          <p className="text-xs text-muted-foreground">
            Messages submitted from the console Support panel (newest first).
            {!showingAll && (
              <span className="block pt-1 text-[10px] text-muted-foreground/80">
                Showing the {ADMIN_FEEDBACK_PAGE_SIZE} most recent of {total}.
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground tabular-nums">{total} total</span>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className="rounded border border-border/30 bg-card px-3 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-card/80 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {isError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-xs text-destructive">
          Failed to load feedback. Check server connectivity.
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-border/20">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-border/20 bg-card">
              <th className="px-3 py-2.5 font-semibold uppercase tracking-wider text-muted-foreground">Time</th>
              <th className="px-3 py-2.5 font-semibold uppercase tracking-wider text-muted-foreground">User</th>
              <th className="px-3 py-2.5 font-semibold uppercase tracking-wider text-muted-foreground">Email</th>
              <th className="px-3 py-2.5 font-semibold uppercase tracking-wider text-muted-foreground">Message</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-12 text-center text-muted-foreground">
                  <MessageSquareText className="mx-auto mb-2 size-8 opacity-40" />
                  No feedback yet.
                </td>
              </tr>
            )}
            {!isLoading &&
              items.map((row) => (
                <tr key={row.id} className="border-b border-border/10 align-top hover:bg-accent/30">
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground tabular-nums">
                    {formatTimestamp(row.gmt_created)}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-2.5 font-mono text-[10px] text-foreground">
                    {row.user_id}
                  </td>
                  <td className="max-w-[180px] truncate px-3 py-2.5 text-muted-foreground">{row.email}</td>
                  <td className="px-3 py-2.5 text-foreground">
                    <span className="whitespace-pre-wrap break-words">{row.body}</span>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
