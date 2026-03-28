import { Outlet, Link } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"

export function PublicLayout() {
  const { data: user, isLoading } = useCurrentUser()
  const consoleLabel = !isLoading && user ? "Dashboard" : "Sign In"
  const consoleHref = !isLoading && user ? "/app" : "/auth/sign-in"
  const primaryCta = !isLoading && user
    ? { to: "/app", label: "Open Console" }
    : { to: "/auth/sign-up", label: "Start Free" }

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <Link
            to="/"
            className="text-sm font-bold uppercase tracking-widest text-primary"
          >
            Treadstone
          </Link>
          <nav className="flex items-center gap-6">
            <a
              href="/#platform-features"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Features
            </a>
            <a
              href="/#install-cli"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Install CLI
            </a>
            <Link
              to={consoleHref}
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              {consoleLabel}
            </Link>
          </nav>
        </div>
        <Link
          to={primaryCta.to}
          className="bg-primary px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {primaryCta.label}
        </Link>
      </header>
      <Outlet />
    </div>
  )
}
