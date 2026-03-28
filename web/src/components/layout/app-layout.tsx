import { useState } from "react"
import { Outlet, Navigate } from "react-router"
import { toast } from "sonner"
import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { useCurrentUser, useRequestVerification } from "@/hooks/use-auth"
import { HttpError } from "@/lib/api-client"
import { APP_VERSION } from "@/lib/app-version"

function VerificationBanner() {
  const resend = useRequestVerification()
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  return (
    <div className="flex items-center justify-between gap-4 border-b border-amber-500/30 bg-amber-500/10 px-6 py-3">
      <p className="text-sm text-amber-200">
        Please verify your email to create sandboxes. Check your inbox for a verification link.
      </p>
      <div className="flex shrink-0 items-center gap-3">
        <button
          type="button"
          disabled={resend.isPending}
          onClick={async () => {
            try {
              await resend.mutateAsync()
              toast.success("Verification email sent.")
            } catch (err) {
              const msg = err instanceof HttpError ? err.message : "Could not resend."
              toast.error(msg)
            }
          }}
          className="text-xs font-semibold uppercase tracking-wider text-amber-300 transition-colors hover:text-amber-100 disabled:opacity-50"
        >
          {resend.isPending ? "Sending…" : "Resend"}
        </button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="text-amber-400/60 transition-colors hover:text-amber-200"
          aria-label="Dismiss"
        >
          ✕
        </button>
      </div>
    </div>
  )
}

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
        {!user.is_verified && <VerificationBanner />}
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
