import { Outlet, Link, Navigate, useLocation } from "react-router"
import { useCurrentUser } from "@/hooks/use-auth"
import { TreadstoneLockup } from "@/components/brand/logo"

/** Must allow logged-in users to stay on token-based auth routes so links from email can complete. */
function isTokenActionPath(pathname: string): boolean {
  return (
    pathname === "/auth/verify-email" ||
    pathname.endsWith("/auth/verify-email") ||
    pathname === "/auth/reset-password" ||
    pathname.endsWith("/auth/reset-password")
  )
}

export function AuthLayout() {
  const { data: user, isLoading } = useCurrentUser()
  const location = useLocation()
  const onTokenAction = isTokenActionPath(location.pathname)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-sm text-muted-foreground">Loading…</div>
      </div>
    )
  }

  if (user && !onTokenAction) {
    return <Navigate to="/app" replace />
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <Link to="/" className="mb-8 text-xl text-foreground transition-opacity hover:opacity-80">
        <TreadstoneLockup />
      </Link>
      <div className="w-full max-w-sm">
        <Outlet />
      </div>
    </div>
  )
}
