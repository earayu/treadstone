import { useCurrentUser, useLogout } from "@/hooks/use-auth"

export function Topbar() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-6">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-muted-foreground">{user.email}</span>
            <button
              onClick={() => logout.mutate()}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Sign out
            </button>
          </>
        )}
      </div>
    </header>
  )
}
