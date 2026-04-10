import { useEffect, useState, type FormEvent } from "react"
import { Link, useNavigate, useSearchParams } from "react-router"
import { toast } from "sonner"

import { useAppConfig } from "@/api/config"
import { useCurrentUser, useLogin } from "@/hooks/use-auth"
import { HttpError } from "@/lib/api-client"
import { GitHubGlyph, GoogleGlyph, OAuthDivider } from "@/components/auth/shared"
import { inputClassName, oauthAuthorizeUrl } from "@/components/auth/utils"

export function SignInPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const login = useLogin()
  const { data: currentUser, isLoading: userLoading } = useCurrentUser()
  const { data: config, isLoading: configLoading } = useAppConfig()

  const returnTo = searchParams.get("return_to")
  const errorParam = searchParams.get("error")

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  useEffect(() => {
    if (errorParam) toast.error(errorParam)
  }, [errorParam])

  useEffect(() => {
    if (userLoading) return
    if (!currentUser) return
    if (returnTo) {
      window.location.assign(`/v1/browser/bootstrap?return_to=${encodeURIComponent(returnTo)}`)
    } else {
      navigate("/app", { replace: true })
    }
  }, [currentUser, userLoading, returnTo, navigate])

  const googleOAuthEnabled = config?.auth.login_methods.includes("google") ?? false
  const githubOAuthEnabled = config?.auth.login_methods.includes("github") ?? false
  const showOAuth = !configLoading && (googleOAuthEnabled || githubOAuthEnabled)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await login.mutateAsync({ email: email.trim(), password })
      toast.success("Signed in successfully.")
      if (returnTo) {
        window.location.assign(`/v1/browser/bootstrap?return_to=${encodeURIComponent(returnTo)}`)
      } else {
        navigate("/app")
      }
    } catch (err) {
      if (err instanceof HttpError) {
        toast.error(err.message)
      } else {
        toast.error("Sign in failed. Please try again.")
      }
    }
  }

  return (
    <div className="pb-10">
      <h1 className="text-center text-4xl font-bold tracking-tight text-foreground">Sign in</h1>
      <p className="mt-3 text-center text-sm leading-relaxed text-muted-foreground">
        This account manages sandboxes, API keys, usage credits, and browser hand-off links.
      </p>

      {showOAuth ? (
        <div className={`mt-8 grid gap-3 ${googleOAuthEnabled && githubOAuthEnabled ? "grid-cols-2" : "grid-cols-1"}`}>
          {googleOAuthEnabled ? (
            <button
              type="button"
              className="flex h-11 items-center justify-center gap-2 rounded-md border border-border bg-secondary text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
              onClick={() => {
                window.location.assign(oauthAuthorizeUrl("google", returnTo))
              }}
            >
              <GoogleGlyph className="size-4 shrink-0" />
              Google
            </button>
          ) : null}
          {githubOAuthEnabled ? (
            <button
              type="button"
              className="flex h-11 items-center justify-center gap-2 rounded-md border border-border bg-secondary text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
              onClick={() => {
                window.location.assign(oauthAuthorizeUrl("github", returnTo))
              }}
            >
              <GitHubGlyph className="size-4 shrink-0" />
              GitHub
            </button>
          ) : null}
        </div>
      ) : null}

      <OAuthDivider label={showOAuth ? "Or sign in with email" : "Sign in with email"} />

      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label htmlFor="sign-in-email" className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Email
          </label>
          <input
            id="sign-in-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@example.com"
            className={inputClassName}
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="sign-in-password"
            className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
          >
            Password
          </label>
          <input
            id="sign-in-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className={inputClassName}
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
          />
        </div>

        <button
          type="submit"
          disabled={login.isPending}
          className="flex h-11 w-full items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-50"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-10 text-center text-[10px] font-medium uppercase leading-relaxed tracking-[0.12em] text-muted-foreground">
        By signing in, you agree to the Terms of Service and Privacy Policy.
      </p>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        <Link to="/auth/forgot-password" className="font-medium text-foreground underline-offset-4 hover:underline">
          Forgot password?
        </Link>
      </p>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Need an account?{" "}
        <Link to="/auth/sign-up" className="font-medium text-foreground underline-offset-4 hover:underline">
          Create one
        </Link>
      </p>

      <footer className="mt-12 flex flex-col gap-3 border-t border-border pt-6 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <span>© 2026 Treadstone</span>
        <div className="flex flex-wrap gap-x-4 gap-y-1 sm:justify-end">
          <Link to="/" className="transition-colors hover:text-foreground">
            Home
          </Link>
          <a href="/#quickstart-step-1" className="transition-colors hover:text-foreground">
            Install CLI
          </a>
        </div>
      </footer>
    </div>
  )
}
