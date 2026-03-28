import { useEffect, useRef } from "react"
import { Link, useSearchParams } from "react-router"

import { useConfirmVerification } from "@/hooks/use-auth"

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  const confirm = useConfirmVerification()
  const calledRef = useRef(false)

  useEffect(() => {
    if (!token || calledRef.current) return
    calledRef.current = true
    confirm.mutate({ token })
    // confirm.mutate is stable across renders; token-only dependency is intentional
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (!token) {
    return (
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Invalid Link</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          No verification token found. Please check the link in your email.
        </p>
        <Link
          to="/auth/sign-in"
          className="mt-8 inline-block bg-primary px-6 py-2.5 text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Sign In
        </Link>
      </div>
    )
  }

  if (confirm.isPending) {
    return (
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Verifying...</h1>
        <p className="mt-3 text-sm text-muted-foreground">Please wait while we verify your email.</p>
      </div>
    )
  }

  if (confirm.isError) {
    return (
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Verification Failed</h1>
        <p className="mt-3 text-sm text-muted-foreground">
          This link may have expired or already been used. Please request a new verification email.
        </p>
        <Link
          to="/app"
          className="mt-8 inline-block bg-primary px-6 py-2.5 text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Go to Dashboard
        </Link>
      </div>
    )
  }

  return (
    <div className="text-center">
      <h1 className="text-3xl font-bold tracking-tight text-foreground">Email Verified</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        Your email has been verified. You can now create sandboxes.
      </p>
      <Link
        to="/app"
        className="mt-8 inline-block bg-primary px-6 py-2.5 text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Go to Dashboard
      </Link>
    </div>
  )
}
