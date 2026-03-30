import { useState, useRef, useEffect } from "react"
import { Link, useLocation, useNavigate } from "react-router"
import { Mail, User, Settings, LogOut, BookOpen } from "lucide-react"
import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { useSubmitFeedback } from "@/api/support"
import { toast } from "sonner"

const GITHUB_URL = "https://github.com/earayu/treadstone"
const SUPPORT_EMAIL = "support@treadstone-ai.dev"

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 98 96"
      xmlns="http://www.w3.org/2000/svg"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405 46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127-13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17-4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052 4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6-10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2-.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63 9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038 3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283 1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526 0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691C97.707 22 75.788 0 48.854 0z"
      />
    </svg>
  )
}

const ROUTE_LABELS: Record<string, string> = {
  "/app": "Sandboxes",
  "/app/api-keys": "API Keys",
  "/app/usage": "Usage",
  "/app/settings": "Settings",
  "/app/sandboxes/new": "Create Sandbox",
}

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

  const pageLabel = location.pathname.startsWith("/app/sandboxes/")
    ? "Sandbox Detail"
    : (ROUTE_LABELS[location.pathname] ?? "Console")

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
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest">
        <Link
          to="/app"
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          Console
        </Link>
        <span className="text-muted-foreground">&rsaquo;</span>
        <span className="font-medium text-foreground">{pageLabel}</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 border-r border-border/30 pr-6">
          <Link
            to="/docs"
            aria-label="Documentation"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <BookOpen className="size-4" />
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="GitHub"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <GithubIcon className="size-4" />
          </a>

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
