import { Link, useLocation } from "react-router"
import { HelpCircle, Bell, User } from "lucide-react"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"

const ROUTE_LABELS: Record<string, string> = {
  "/app": "Sandboxes",
  "/app/api-keys": "API Keys",
  "/app/templates": "Templates",
  "/app/usage": "Usage",
  "/app/settings": "Settings",
  "/app/sandboxes/new": "Create Sandbox",
}

export function Topbar() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const location = useLocation()

  const pageLabel = ROUTE_LABELS[location.pathname] ?? "Console"

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest">
        <span className="text-muted-foreground">Console</span>
        <span className="text-muted-foreground">&rsaquo;</span>
        <span className="font-medium text-foreground">{pageLabel}</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 border-r border-border/30 pr-6">
          <button className="text-muted-foreground transition-colors hover:text-foreground">
            <HelpCircle className="size-4" />
          </button>
          <button className="text-muted-foreground transition-colors hover:text-foreground">
            <Bell className="size-4" />
          </button>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="/quickstart"
            className="text-xs uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
          >
            Docs
          </a>
          <Link
            to="/app/sandboxes/new"
            className="bg-secondary px-3 py-1.5 text-xs font-medium uppercase tracking-widest text-secondary-foreground transition-colors hover:bg-secondary/80"
          >
            Create Sandbox
          </Link>
          {user && (
            <button
              onClick={() => logout.mutate()}
              className="flex size-7 items-center justify-center border border-border/30 bg-accent text-muted-foreground transition-colors hover:text-foreground"
            >
              <User className="size-3" />
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
