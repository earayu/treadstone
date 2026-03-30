import { useMemo } from "react"
import { Search, ChevronLeft, ChevronRight } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
  ADMIN_USERS_PAGE_SIZE,
  useAdminUsersListState,
  useAdminUpdateUserStatus,
  type UserItem,
} from "@/api/admin"
import { useCurrentUser } from "@/hooks/use-auth"

function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        isActive
          ? "bg-emerald-500/10 text-emerald-400"
          : "bg-destructive/10 text-destructive",
      )}
    >
      <span className={cn("size-1.5 rounded-full", isActive ? "bg-emerald-400" : "bg-destructive")} />
      {isActive ? "Active" : "Disabled"}
    </span>
  )
}

function RoleBadge({ role }: { role: string }) {
  const isAdmin = role === "admin"
  return (
    <span
      className={cn(
        "inline-flex rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        isAdmin ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
      )}
    >
      {role}
    </span>
  )
}

function UserRow({
  user,
  isSelf,
  onToggleStatus,
  isPending,
}: {
  user: UserItem
  isSelf: boolean
  onToggleStatus: (userId: string, newStatus: boolean) => void
  isPending: boolean
}) {
  return (
    <tr className="border-b border-border/15 transition-colors hover:bg-card/50">
      <td className="px-5 py-3 text-xs text-foreground">{user.email}</td>
      <td className="px-5 py-3">
        <RoleBadge role={user.role} />
      </td>
      <td className="px-5 py-3">
        <StatusBadge isActive={user.is_active} />
      </td>
      <td className="px-5 py-3 font-mono text-[10px] text-muted-foreground">{user.id}</td>
      <td className="px-5 py-3">
        {isSelf ? (
          <span className="text-[10px] text-muted-foreground/50">—</span>
        ) : (
          <button
            onClick={() => {
              const action = user.is_active ? "disable" : "enable"
              if (window.confirm(`Are you sure you want to ${action} ${user.email}?`)) {
                onToggleStatus(user.id, !user.is_active)
              }
            }}
            disabled={isPending}
            className={cn(
              "rounded-sm border px-3 py-1 text-[11px] font-medium transition-colors disabled:opacity-50",
              user.is_active
                ? "border-destructive/40 text-destructive hover:bg-destructive/10"
                : "border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10",
            )}
          >
            {user.is_active ? "Disable" : "Enable"}
          </button>
        )}
      </td>
    </tr>
  )
}

export function AdminUsersPage() {
  const { data: currentUser } = useCurrentUser()
  const {
    data,
    isLoading,
    isError,
    refetch,
    page,
    setPage,
    emailInput,
    setEmailInput,
    debouncedEmail,
  } = useAdminUsersListState()
  const updateStatus = useAdminUpdateUserStatus()
  const users = data?.items ?? []
  const total = data?.total ?? 0

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / ADMIN_USERS_PAGE_SIZE)),
    [total],
  )

  const rangeLabel = useMemo(() => {
    if (total === 0) return "No users"
    const start = page * ADMIN_USERS_PAGE_SIZE + 1
    const end = Math.min((page + 1) * ADMIN_USERS_PAGE_SIZE, total)
    return `Showing ${start}–${end} of ${total}`
  }, [total, page])

  const handleToggleStatus = (userId: string, newStatus: boolean) => {
    updateStatus.mutate(
      { userId, isActive: newStatus },
      {
        onSuccess: (res) => toast.success(res.detail),
        onError: (e) => toast.error(e.message),
      },
    )
  }

  const columns = [
    { label: "EMAIL", className: "w-[30%]" },
    { label: "ROLE", className: "w-[12%]" },
    { label: "STATUS", className: "w-[14%]" },
    { label: "USER ID", className: "w-[28%]" },
    { label: "ACTIONS", className: "w-[16%]" },
  ] as const

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">User Management</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          View all registered users and manage account status.
        </p>
      </div>

      <div className="rounded border border-border/20 bg-black">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/20 bg-card px-5 py-4">
          <span className="text-[11px] font-medium uppercase tracking-[1.5px] text-muted-foreground">
            ALL USERS
          </span>
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground/60" />
              <input
                type="search"
                placeholder="Search by email…"
                value={emailInput}
                onChange={(e) => {
                  setPage(0)
                  setEmailInput(e.target.value)
                }}
                className="h-8 w-56 bg-background pl-8 pr-3 text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-ring"
                aria-label="Filter users by email"
              />
            </div>
            {data !== undefined && (
              <span className="text-[11px] text-muted-foreground/60">
                {debouncedEmail ? `${total} match${total !== 1 ? "es" : ""}` : `${total} user${total !== 1 ? "s" : ""}`}
              </span>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]">
            <thead>
              <tr className="border-b border-border/20 bg-card">
                {columns.map((col) => (
                  <th
                    key={col.label}
                    className={cn(
                      "px-5 py-2.5 text-left text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground",
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
                  <td colSpan={5} className="px-5 py-10 text-center text-sm text-muted-foreground">
                    Loading...
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-sm text-destructive">
                    Failed to load users.{" "}
                    <button onClick={() => refetch()} className="underline hover:text-destructive/80">
                      Retry
                    </button>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-sm text-muted-foreground">
                    No users found.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    isSelf={user.id === currentUser?.id}
                    onToggleStatus={handleToggleStatus}
                    isPending={updateStatus.isPending}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-border/20 bg-card px-5 py-3">
          <span className="text-[10px] uppercase tracking-[1px] text-muted-foreground">{rangeLabel}</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || isLoading}
              className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
              aria-label="Previous page"
            >
              <ChevronLeft className="size-3" />
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || isLoading || total === 0}
              className="flex size-8 items-center justify-center border border-border/30 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
              aria-label="Next page"
            >
              <ChevronRight className="size-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
