import { Outlet, Link } from "react-router"

export function PublicLayout() {
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
            <Link
              to="/"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Features
            </Link>
            <Link
              to="/app"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Dashboard
            </Link>
            <Link
              to="/quickstart"
              className="text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              Docs
            </Link>
          </nav>
        </div>
        <Link
          to="/auth/sign-up"
          className="bg-primary px-4 py-1.5 text-xs font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Start Free
        </Link>
      </header>
      <Outlet />
    </div>
  )
}
