import { Outlet, Navigate } from "react-router"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { useCurrentUser } from "@/hooks/use-auth"
import { APP_VERSION } from "@/lib/app-version"

export function AppLayout() {
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

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
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
