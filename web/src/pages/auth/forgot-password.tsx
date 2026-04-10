import { useState, type FormEvent } from "react"
import { Link } from "react-router"

import { inputClassName } from "@/components/auth/utils"

type ApiError = {
  error?: {
    code?: string
    message?: string
  }
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setSuccessMessage(null)
    setErrorMessage(null)

    try {
      const response = await fetch("/v1/auth/password-reset/request", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      })
      const body = (await response.json().catch(() => null)) as { detail?: string } & ApiError
      if (!response.ok) {
        setErrorMessage(body.error?.message ?? "Could not send a reset link.")
        return
      }
      setSuccessMessage(body.detail ?? "If an account exists, we sent a password reset link.")
    } catch {
      setErrorMessage("Could not send a reset link.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="pb-10">
      <h1 className="text-center text-4xl font-bold tracking-tight text-foreground">Forgot password</h1>
      <p className="mt-3 text-center text-sm leading-relaxed text-muted-foreground">
        Enter your email and we&apos;ll send you a reset link if the account supports password sign-in.
      </p>

      <form className="mt-10 space-y-5" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label
            htmlFor="forgot-password-email"
            className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
          >
            Email
          </label>
          <input
            id="forgot-password-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@example.com"
            className={inputClassName}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        {successMessage ? (
          <p className="rounded-md border border-border bg-secondary px-4 py-3 text-sm text-secondary-foreground">
            {successMessage}
          </p>
        ) : null}

        {errorMessage ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {errorMessage}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="flex h-11 w-full items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send reset link"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link to="/auth/sign-in" className="font-medium text-foreground underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
