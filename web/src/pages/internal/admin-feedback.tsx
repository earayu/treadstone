import * as Dialog from "@radix-ui/react-dialog"
import { MessageSquareText } from "lucide-react"
import { useEffect, useState } from "react"
import { ADMIN_FEEDBACK_PAGE_SIZE, type FeedbackItem, useAdminFeedbackList } from "@/api/support"

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

function FeedbackDetailDialog({
  item,
  onClose,
}: {
  item: FeedbackItem | null
  onClose: () => void
}) {
  const open = item !== null
  return (
    <Dialog.Root open={open} onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(100vw-2rem,560px)] max-h-[min(90vh,720px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto border border-border/20 bg-card p-6 shadow-xl outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
          <Dialog.Title className="text-base font-semibold text-foreground">Feedback detail</Dialog.Title>
          <Dialog.Description className="sr-only">Full message and metadata for this feedback entry.</Dialog.Description>
          {item && (
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Time</div>
                <div className="mt-0.5 tabular-nums text-foreground">{formatTimestamp(item.gmt_created)}</div>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">User ID</div>
                <div className="mt-0.5 break-all font-mono text-[11px] text-foreground">{item.user_id}</div>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Email</div>
                <div className="mt-0.5 break-all text-foreground">{item.email}</div>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Message</div>
                <pre className="mt-1 max-h-[50vh] overflow-y-auto whitespace-pre-wrap break-words rounded border border-border/15 bg-muted/30 p-3 text-[13px] leading-relaxed text-foreground">
                  {item.body}
                </pre>
              </div>
            </div>
          )}
          <Dialog.Close className="mt-6 rounded border border-border/40 bg-secondary px-4 py-2 text-xs font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80">
            Close
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function AdminFeedbackPage() {
  const [emailDraft, setEmailDraft] = useState("")
  const [emailQuery, setEmailQuery] = useState("")
  const [selected, setSelected] = useState<FeedbackItem | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setEmailQuery(emailDraft.trim()), 350)
    return () => clearTimeout(t)
  }, [emailDraft])

  const { data, isLoading, isError, isFetching, refetch } = useAdminFeedbackList(emailQuery)

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const showingAll = total <= ADMIN_FEEDBACK_PAGE_SIZE

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-foreground">Support feedback</h1>
          <p className="text-xs text-muted-foreground">
            Messages from the console Support panel, newest first (by submission time).
            {!showingAll && (
              <span className="block pt-1 text-[10px] text-muted-foreground/80">
                {emailQuery
                  ? `Showing up to ${ADMIN_FEEDBACK_PAGE_SIZE} of ${total} matching “${emailQuery}”.`
                  : `Showing the ${ADMIN_FEEDBACK_PAGE_SIZE} most recent of ${total}.`}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          <label className="flex flex-col gap-1 text-left sm:items-end">
            <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Filter by email</span>
            <input
              type="search"
              value={emailDraft}
              onChange={(e) => setEmailDraft(e.target.value)}
              placeholder="Substring match, e.g. @company.com"
              autoComplete="off"
              className="w-full min-w-[220px] rounded border border-border/30 bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:border-border focus:outline-none focus:ring-1 focus:ring-border/50 sm:max-w-xs"
            />
          </label>
          <div className="flex items-center justify-end gap-2">
            <span className="text-[10px] text-muted-foreground tabular-nums">{total} matching</span>
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
                  {emailQuery ? "No feedback matches this email filter." : "No feedback yet."}
                </td>
              </tr>
            )}
            {!isLoading &&
              items.map((row) => (
                <tr
                  key={row.id}
                  className="group border-b border-border/10 align-top hover:bg-accent/30"
                >
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground tabular-nums">
                    {formatTimestamp(row.gmt_created)}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-2.5 font-mono text-[10px] text-foreground">
                    {row.user_id}
                  </td>
                  <td className="max-w-[180px] truncate px-3 py-2.5 text-muted-foreground">{row.email}</td>
                  <td className="max-w-0 px-3 py-2.5">
                    <button
                      type="button"
                      onClick={() => setSelected(row)}
                      className="w-full text-left text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border/50"
                    >
                      <span className="line-clamp-3 whitespace-pre-wrap break-words">{row.body}</span>
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      <FeedbackDetailDialog item={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
