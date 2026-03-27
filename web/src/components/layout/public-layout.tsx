import { Outlet, Link } from "react-router"

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <Link to="/" className="text-lg font-semibold tracking-tight text-foreground">
          Treadstone
        </Link>
        <nav className="flex items-center gap-6">
          <Link to="/pricing" className="text-sm text-muted-foreground hover:text-foreground">
            Pricing
          </Link>
          <Link to="/quickstart" className="text-sm text-muted-foreground hover:text-foreground">
            Quickstart
          </Link>
          <Link
            to="/auth/sign-in"
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Sign in
          </Link>
        </nav>
      </header>
      <Outlet />
    </div>
  )
}
