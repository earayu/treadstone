import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"

import { useAppConfig } from "@/api/config"
import { useLogin } from "@/hooks/use-auth"
import { HttpError } from "@/lib/api-client"

const inputClassName =
  "w-full rounded-md border border-border bg-card px-3 py-2.5 text-sm text-foreground shadow-sm transition-[color,box-shadow] outline-none placeholder:text-muted-foreground/40 focus:ring-1 focus:ring-ring"

function GitHubGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 0 0 7.86 10.9c.58.11.79-.25.79-.55 0-.27-.01-1.16-.01-2.1-3.2.7-3.87-1.37-4.12-2.61-.14-.35-.74-1.44-1.27-1.73-.43-.23-1.05-.8-.01-.82.97-.02 1.66.9 1.89 1.27 1.1 1.85 2.86 1.33 3.56 1.01.11-.8.43-1.33.78-1.64-2.73-.31-5.6-1.37-5.6-6.08 0-1.34.48-2.44 1.27-3.3-.13-.31-.55-1.57.12-3.28 0 0 1.03-.33 3.38 1.26a11.5 11.5 0 0 0 6.02 0c2.35-1.59 3.38-1.26 3.38-1.26.67 1.71.25 2.97.12 3.28.79.86 1.27 1.96 1.27 3.3 0 4.72-2.87 5.76-5.61 6.07.44.38.83 1.13.83 2.28 0 1.65-.02 2.98-.02 3.38 0 .33.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"
      />
    </svg>
  )
}

function GoogleGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  )
}

function oauthAuthorizeUrl(provider: "google" | "github"): string {
  return `/v1/auth/${provider}/authorize`
}

export function SignInPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const { data: config, isLoading: configLoading } = useAppConfig()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const googleOAuthEnabled = config?.auth.login_methods.includes("google") ?? false
  const githubOAuthEnabled = config?.auth.login_methods.includes("github") ?? false
  const showOAuth = !configLoading && (googleOAuthEnabled || githubOAuthEnabled)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      await login.mutateAsync({ email: email.trim(), password })
      toast.success("Signed in successfully.")
      navigate("/app")
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
      <h1 className="text-4xl font-bold tracking-tight text-foreground">Sign in</h1>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        This account manages sandboxes, API keys, usage credits, and browser hand-off links.
      </p>

      <form className="mt-8 space-y-5" onSubmit={onSubmit}>
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
          className="flex h-11 w-full items-center justify-center rounded-md bg-primary text-sm font-semibold uppercase tracking-[0.15em] text-primary-foreground transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-50"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {showOAuth ? (
        <>
          <div className="relative my-8">
            <div className="absolute inset-0 flex items-center" aria-hidden>
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-[10px] font-semibold uppercase tracking-[0.2em]">
              <span className="bg-background px-3 text-muted-foreground">Or continue with</span>
            </div>
          </div>

          <div
            className={`grid gap-3 ${googleOAuthEnabled && githubOAuthEnabled ? "grid-cols-2" : "grid-cols-1"}`}
          >
            {googleOAuthEnabled ? (
              <button
                type="button"
                className="flex h-11 items-center justify-center gap-2 rounded-md border border-border bg-secondary text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent"
                onClick={() => {
                  window.location.assign(oauthAuthorizeUrl("google"))
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
                  window.location.assign(oauthAuthorizeUrl("github"))
                }}
              >
                <GitHubGlyph className="size-4 shrink-0" />
                GitHub
              </button>
            ) : null}
          </div>
        </>
      ) : null}

      <p className="mt-10 text-center text-[10px] font-medium uppercase leading-relaxed tracking-[0.12em] text-muted-foreground">
        By signing in, you agree to our{" "}
        <Link to="/#terms" className="text-foreground underline underline-offset-2 hover:opacity-80">
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link to="/#privacy" className="text-foreground underline underline-offset-2 hover:opacity-80">
          Privacy Policy
        </Link>
        .
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
          <Link to="/pricing" className="transition-colors hover:text-foreground">
            Pricing
          </Link>
          <Link to="/quickstart" className="transition-colors hover:text-foreground">
            Quickstart
          </Link>
        </div>
      </footer>
    </div>
  )
}
