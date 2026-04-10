import { useState, useRef, useEffect } from "react"
import { Link, useLocation, useMatch, useNavigate } from "react-router"
import { Mail, User, Settings, LogOut } from "lucide-react"
import { useSandbox } from "@/api/sandboxes"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { useSubmitFeedback } from "@/api/support"
import { toast } from "sonner"

const SUPPORT_EMAIL = "support@treadstone-ai.dev"

const ROUTE_LABELS: Record<string, string> = {
  "/app": "Sandboxes",
  "/app/api-keys": "API Keys",
  "/app/usage": "Usage",
  "/app/settings": "Settings",
}

const crumbLinkClass = "text-muted-foreground transition-colors hover:text-foreground"

function useClickOutside(ref: React.RefObject<HTMLElement | null>, handler: () => void) {
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        handler()
      }
    }
    document.addEventListener("mousedown", onMouseDown)
    return () => document.removeEventListener("mousedown", onMouseDown)
  }, [ref, handler])
}

export function Topbar() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const location = useLocation()
  const navigate = useNavigate()

  const [mailOpen, setMailOpen] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState("")
  const submitFeedback = useSubmitFeedback()

  const mailRef = useRef<HTMLDivElement>(null)
  const userRef = useRef<HTMLDivElement>(null)

  useClickOutside(mailRef, () => setMailOpen(false))
  useClickOutside(userRef, () => setUserOpen(false))

  const sandboxDetailMatch = useMatch({ path: "/app/sandboxes/:id", end: true })
  const sandboxDetailId = sandboxDetailMatch?.params.id
  const isSandboxDetail = Boolean(sandboxDetailId && sandboxDetailId !== "new")
  const { data: sandboxBreadcrumb } = useSandbox(isSandboxDetail && sandboxDetailId ? sandboxDetailId : "")

  const path = location.pathname
  const pageLabel = ROUTE_LABELS[path] ?? "Console"

  const sandboxDetailLabel =
    sandboxBreadcrumb?.name?.trim() || sandboxBreadcrumb?.id || sandboxDetailId || "Sandbox"

  async function handleFeedbackSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = feedbackText.trim()
    if (!trimmed) {
      toast.error("Please enter a message.")
      return
    }
    try {
      await submitFeedback.mutateAsync({ body: trimmed })
      toast.success("Thanks — we received your message.")
      setFeedbackText("")
      setMailOpen(false)
    } catch {
      toast.error("Could not send feedback. Try again or use email.")
    }
  }

  async function handleSignOut() {
    try {
      await logout.mutateAsync()
      toast.success("Signed out.")
      navigate("/auth/sign-in", { replace: true })
    } catch {
      toast.error("Sign out failed.")
    }
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs uppercase tracking-widest">
        <Link to="/app" className={crumbLinkClass}>
          Console
        </Link>
        <span className="text-muted-foreground">&rsaquo;</span>
        {path === "/app/sandboxes/new" ? (
          <>
            <Link to="/app" className={crumbLinkClass}>
              Sandboxes
            </Link>
            <span className="text-muted-foreground">&rsaquo;</span>
            <span className="min-w-0 truncate font-medium text-foreground">Create</span>
          </>
        ) : isSandboxDetail ? (
          <>
            <Link to="/app" className={crumbLinkClass}>
              Sandboxes
            </Link>
            <span className="text-muted-foreground">&rsaquo;</span>
            <span
              className="min-w-0 max-w-[min(52vw,320px)] truncate font-medium text-foreground"
              title={sandboxDetailLabel}
            >
              {sandboxDetailLabel}
            </span>
          </>
        ) : (
          <span className="min-w-0 truncate font-medium text-foreground">{pageLabel}</span>
        )}
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 border-r border-border/30 pr-6">
          <Link
            to="/docs"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            Docs
          </Link>

          {/* Mail / support popover */}
          <div ref={mailRef} className="relative">
            <button
              onClick={() => setMailOpen((v) => !v)}
              aria-label="Contact support"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              <Mail className="size-4" />
            </button>
            {mailOpen && (
              <div className="absolute right-0 top-8 z-50 w-80 border border-border/30 bg-popover p-4 shadow-lg">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Support</p>
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="mt-2 block text-sm font-medium text-primary transition-colors hover:text-primary/80"
                >
                  {SUPPORT_EMAIL}
                </a>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Or send a message from the console (linked to your account). You can still email us directly.
                </p>
                <form onSubmit={(e) => void handleFeedbackSubmit(e)} className="mt-3 flex flex-col gap-2">
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    placeholder="Describe your issue or feedback…"
                    rows={4}
                    maxLength={10_000}
                    disabled={submitFeedback.isPending}
                    className="resize-y rounded-sm border border-border/40 bg-background px-2.5 py-2 text-xs text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={submitFeedback.isPending}
                    className="rounded-sm bg-primary px-3 py-2 text-xs font-semibold uppercase tracking-wider text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                  >
                    {submitFeedback.isPending ? "Sending…" : "Submit"}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* User avatar dropdown */}
          {user && (
            <div ref={userRef} className="relative">
              <button
                onClick={() => setUserOpen((v) => !v)}
                aria-label="User menu"
                className="flex size-7 items-center justify-center border border-border/30 bg-accent text-muted-foreground transition-colors hover:text-foreground"
              >
                <User className="size-3" />
              </button>
              {userOpen && (
                <div className="absolute right-0 top-9 z-50 w-52 border border-border/30 bg-popover shadow-lg">
                  <div className="border-b border-border/20 px-4 py-3">
                    <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                  </div>
                  <div className="py-1">
                    <Link
                      to="/app/settings"
                      onClick={() => setUserOpen(false)}
                      className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-accent"
                    >
                      <Settings className="size-3.5 text-muted-foreground" />
                      Settings
                    </Link>
                    <button
                      onClick={() => void handleSignOut()}
                      disabled={logout.isPending}
                      className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-foreground transition-colors hover:bg-accent disabled:opacity-50"
                    >
                      <LogOut className="size-3.5 text-muted-foreground" />
                      {logout.isPending ? "Signing out…" : "Sign out"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
