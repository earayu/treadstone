import { useCallback, useEffect, useState } from "react"
import { useSearchParams } from "react-router"

import { client } from "@/lib/api-client"

type FlowStatus = "pending" | "approved" | "expired" | "used" | "failed" | string

function parseStatus(data: unknown): FlowStatus {
  if (data && typeof data === "object" && "status" in data) {
    const s = (data as { status: string }).status
    return s
  }
  return "pending"
}

export function CliLoginPage() {
  const [searchParams] = useSearchParams()
  const flowId = searchParams.get("flow_id") ?? ""
  const flowSecret =
    searchParams.get("flow_secret") ?? searchParams.get("secret") ?? ""

  const [status, setStatus] = useState<FlowStatus | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const [localSuccess, setLocalSuccess] = useState(false)

  const poll = useCallback(async () => {
    if (!flowId || !flowSecret) return
    try {
      const { data } = await client.GET("/v1/auth/cli/flows/{flow_id}/status", {
        params: { path: { flow_id: flowId } },
        headers: { "x-flow-secret": flowSecret },
      })
      setStatus(parseStatus(data))
      setPollError(null)
    } catch {
      setPollError("Unable to load flow status. Check your link or try again.")
    }
  }, [flowId, flowSecret])

  useEffect(() => {
    if (!flowId) {
      setStatus(null)
      return
    }
    if (!flowSecret) {
      setStatus("pending")
      return
    }
    void poll()
    const t = window.setInterval(() => void poll(), 2000)
    return () => window.clearInterval(t)
  }, [flowId, flowSecret, poll])

  async function handleApprove(e: React.FormEvent) {
    e.preventDefault()
    if (!flowId) return
    setFormError(null)
    setSubmitting(true)
    try {
      const body = new FormData()
      body.set("email", email)
      body.set("password", password)
      body.set("flow_id", flowId)

      const res = await fetch("/v1/auth/cli/login", {
        method: "POST",
        body,
        credentials: "include",
      })

      const text = await res.text()
      if (res.ok && text.includes("Login successful")) {
        setLocalSuccess(true)
        setStatus("approved")
        void poll()
      } else if (res.status === 400 && text.includes("Invalid email or password")) {
        setFormError("Invalid email or password.")
      } else if (!res.ok) {
        setFormError("Sign-in failed. Try again or use OAuth from the API login page.")
      } else {
        setLocalSuccess(true)
        setStatus("approved")
      }
    } catch {
      setFormError("Network error. Check your connection and try again.")
    } finally {
      setSubmitting(false)
    }
  }

  const displayStatus = localSuccess ? "approved" : status ?? (flowId ? "pending" : null)

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md border border-border/20 bg-card p-8 shadow-xl">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">CLI Login</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Approve sign-in for your terminal session.
        </p>

        {!flowId ? (
          <p className="mt-8 text-sm text-destructive">
            Missing <span className="font-mono">flow_id</span> in the URL. Open the link from your CLI.
          </p>
        ) : (
          <>
            <div className="mt-8 rounded border border-border/15 bg-background/50 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                Flow ID
              </p>
              <p className="mt-1 font-mono text-xs break-all text-foreground">{flowId}</p>
            </div>

            <div className="mt-6">
              <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                Status
              </p>
              <p className="mt-2 text-sm capitalize text-foreground">
                {displayStatus ?? "—"}
              </p>
              {pollError && <p className="mt-2 text-sm text-destructive">{pollError}</p>}
              {!flowSecret && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Polling requires <span className="font-mono">flow_secret</span> in the URL (optional). You can
                  still approve with your password below.
                </p>
              )}
            </div>

            {localSuccess || displayStatus === "approved" ? (
              <p className="mt-8 text-sm text-success">
                You can close this window and return to your terminal.
              </p>
            ) : displayStatus === "expired" ? (
              <p className="mt-8 text-sm text-warning">This login link has expired. Run login again in the CLI.</p>
            ) : displayStatus === "used" ? (
              <p className="mt-8 text-sm text-muted-foreground">
                This flow was already used. If the CLI did not receive a token, start a new login.
              </p>
            ) : (
              <form className="mt-8 space-y-4" onSubmit={(e) => void handleApprove(e)}>
                <label className="block">
                  <span className="text-xs font-semibold text-muted-foreground">Email</span>
                  <input
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-muted-foreground">Password</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </label>
                {formError && <p className="text-sm text-destructive">{formError}</p>}
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full bg-primary py-3 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                >
                  {submitting ? "Signing in…" : "Approve login"}
                </button>
                <p className="text-center text-xs text-muted-foreground">or</p>
                <div className="flex flex-col gap-2">
                  <a
                    href={`/v1/auth/google/authorize?cli_flow_id=${encodeURIComponent(flowId)}`}
                    className="flex h-10 items-center justify-center border border-border/40 text-sm font-medium text-foreground hover:bg-accent"
                  >
                    Continue with Google
                  </a>
                  <a
                    href={`/v1/auth/github/authorize?cli_flow_id=${encodeURIComponent(flowId)}`}
                    className="flex h-10 items-center justify-center border border-border/40 text-sm font-medium text-foreground hover:bg-accent"
                  >
                    Continue with GitHub
                  </a>
                </div>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  )
}
