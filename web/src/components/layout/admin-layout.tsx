import { Outlet, Navigate, useLocation } from "react-router"
import { LogOut } from "lucide-react"
import { Sidebar } from "./sidebar"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { APP_VERSION } from "@/lib/app-version"

const ADMIN_ROUTE_LABELS: Record<string, string> = {
  "/internal/admin/overview": "OVERVIEW",
  "/internal/admin/users": "USER MANAGEMENT",
  "/internal/admin/platform-limits": "PLATFORM LIMITS",
  "/internal/admin/metering": "METERING",
  "/internal/admin/feedback": "FEEDBACK",
  "/internal/audit": "AUDIT EVENTS",
}

function AdminTopbar() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const location = useLocation()

  const pageLabel = ADMIN_ROUTE_LABELS[location.pathname] ?? "CONSOLE"

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[1.5px]">
        <span className="font-medium text-muted-foreground">ADMIN</span>
        <span className="text-muted-foreground/50">&rsaquo;</span>
        <span className="font-medium text-foreground">{pageLabel}</span>
      </div>

      <div className="flex items-center gap-3">
        <span className="rounded-sm border border-destructive/50 bg-destructive/15 px-2 py-1 text-[10px] font-medium uppercase tracking-wider text-destructive">
          ADMIN
        </span>
        {user && (
          <button
            onClick={() => logout.mutate()}
            aria-label="Sign out"
            className="flex size-9 items-center justify-center rounded bg-accent text-muted-foreground transition-colors hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        )}
      </div>
    </header>
  )
}

export function AdminLayout() {
  const { data: user, isLoading } = useCurrentUser()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Loading…</div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/auth/sign-in" replace />
  }

  if (user.role !== "admin") {
    return <Navigate to="/app" replace />
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AdminTopbar />
        <main className="relative flex-1 overflow-auto">
          <div className="mx-auto max-w-[1280px] p-8">
            <Outlet />
          </div>
          <footer className="border-t border-border/10 py-6 text-center">
            <span className="text-[10px] uppercase tracking-[3px] text-muted-foreground/60">
              Treadstone&nbsp;&middot;&nbsp;v{APP_VERSION}
            </span>
          </footer>
        </main>
      </div>
    </div>
  )
}
