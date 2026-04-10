import { useMemo, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"

import { inputClassName } from "@/components/auth/utils"

type ApiError = {
  error?: {
    code?: string
    message?: string
  }
}

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")

  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const missingToken = useMemo(() => !token, [token])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token) return
    if (newPassword !== confirmPassword) {
      setErrorMessage("New password and confirmation do not match.")
      return
    }
    if (newPassword.length < 8) {
      setErrorMessage("New password must be at least 8 characters.")
      return
    }

    setSubmitting(true)
    setErrorMessage(null)

    try {
      const response = await fetch("/v1/auth/password-reset/confirm", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const body = (await response.json().catch(() => null)) as { detail?: string } & ApiError
      if (!response.ok) {
        setErrorMessage(body.error?.message ?? "Could not reset your password.")
        return
      }
      toast.success(body.detail ?? "Password reset successful")
      navigate("/auth/sign-in", { replace: true })
    } catch {
      setErrorMessage("Could not reset your password.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="pb-10">
      <h1 className="text-center text-4xl font-bold tracking-tight text-foreground">Reset password</h1>
      <p className="mt-3 text-center text-sm leading-relaxed text-muted-foreground">
        Choose a new password for your Treadstone account.
      </p>

      {missingToken ? (
        <>
          <p className="mt-8 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            No password reset token found. Please use the link from your email.
          </p>
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Need another link?{" "}
            <Link to="/auth/forgot-password" className="font-medium text-foreground underline-offset-4 hover:underline">
              Request a new reset email
            </Link>
          </p>
        </>
      ) : (
        <form className="mt-10 space-y-5" onSubmit={onSubmit}>
          <div className="space-y-2">
            <label
              htmlFor="reset-password-new"
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
            >
              New password
            </label>
            <input
              id="reset-password-new"
              name="new-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              className={inputClassName}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="reset-password-confirm"
              className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
            >
              Confirm new password
            </label>
            <input
              id="reset-password-confirm"
              name="confirm-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              className={inputClassName}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </div>

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
            {submitting ? "Resetting…" : "Reset password"}
          </button>
        </form>
      )}

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Back to{" "}
        <Link to="/auth/sign-in" className="font-medium text-foreground underline-offset-4 hover:underline">
          sign in
        </Link>
      </p>
    </div>
  )
}
