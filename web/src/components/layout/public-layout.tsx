import { Outlet, Link } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"

const GITHUB_URL = "https://github.com/earayu/treadstone"

export function PublicLayout() {
  const { data: user, isLoading } = useCurrentUser()
  const isLoggedIn = !isLoading && !!user

  return (
    <div className="min-h-screen bg-background">
      <header className="flex h-14 items-center justify-between border-b border-border/20 px-16">
        <div className="flex items-center gap-9">
          <Link
            to="/"
            className="text-sm font-semibold tracking-wide text-primary transition-opacity hover:opacity-80"
          >
            Treadstone
          </Link>
          <nav className="flex items-center gap-7">
            <a
              href="/#install-cli"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              Install CLI
            </a>
            <a
              href="/#plans"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              Plans
            </a>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              GitHub
            </a>
          </nav>
        </div>

        {isLoggedIn ? (
          <Link
            to="/app"
            className="rounded px-4 py-1.5 text-sm font-semibold text-primary-foreground bg-primary transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Dashboard
          </Link>
        ) : (
          <Link
            to="/auth/sign-in"
            className="rounded border border-border px-4 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Sign In
          </Link>
        )}
      </header>
      <Outlet />
    </div>
  )
}
