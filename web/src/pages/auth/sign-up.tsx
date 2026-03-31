import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"

import { useAppConfig } from "@/api/config"
import { useRegister } from "@/hooks/use-auth"
import { HttpError } from "@/lib/api-client"
import { GitHubGlyph, GoogleGlyph, OAuthDivider } from "@/components/auth/shared"
import { inputClassName, oauthAuthorizeUrl } from "@/components/auth/utils"

export function SignUpPage() {
  const navigate = useNavigate()
  const register = useRegister()
  const { data: config, isLoading: configLoading } = useAppConfig()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const googleOAuthEnabled = config?.auth.login_methods.includes("google") ?? false
  const githubOAuthEnabled = config?.auth.login_methods.includes("github") ?? false
  const showOAuth = !configLoading && (googleOAuthEnabled || githubOAuthEnabled)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    try {
      const result = await register.mutateAsync({ email: email.trim(), password })
      const r = result as { is_verified?: boolean; verification_email_sent?: boolean }
      if (r.is_verified) {
        toast.success("Account created.")
      } else if (r.verification_email_sent) {
        toast.success("Account created. Check your email to verify your address.")
      } else {
        toast.success("Account created.")
      }
      navigate("/app")
    } catch (err) {
      if (err instanceof HttpError) {
        toast.error(err.message)
      } else {
        toast.error("Registration failed. Please try again.")
      }
    }
  }

  return (
    <div className="pb-10">
      <h1 className="text-center text-4xl font-bold tracking-tight text-foreground">Create Account</h1>
      <p className="mt-3 text-center text-sm leading-relaxed text-muted-foreground">
        Create your Treadstone account to get started.
      </p>

      {showOAuth ? (
        <div className={`mt-8 grid gap-3 ${googleOAuthEnabled && githubOAuthEnabled ? "grid-cols-2" : "grid-cols-1"}`}>
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
      ) : null}

      <OAuthDivider label={showOAuth ? "Or sign up with email" : "Sign up with email"} />

      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label htmlFor="sign-up-email" className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Email
          </label>
          <input
            id="sign-up-email"
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
            htmlFor="sign-up-password"
            className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground"
          >
            Password
          </label>
          <input
            id="sign-up-password"
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            className={inputClassName}
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
          />
        </div>

        <button
          type="submit"
          disabled={register.isPending}
          className="flex h-11 w-full items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-50"
        >
          {register.isPending ? "Creating account…" : "Create Account"}
        </button>
      </form>

      <p className="mt-10 text-center text-[10px] font-medium uppercase leading-relaxed tracking-[0.12em] text-muted-foreground">
        By creating an account, you agree to the Terms of Service and Privacy Policy.
      </p>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/auth/sign-in" className="font-medium text-foreground underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>

      <footer className="mt-12 flex flex-col gap-3 border-t border-border pt-6 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <span>© 2026 Treadstone</span>
        <div className="flex flex-wrap gap-x-4 gap-y-1 sm:justify-end">
          <Link to="/" className="transition-colors hover:text-foreground">
            Home
          </Link>
          <a href="/#install-cli" className="transition-colors hover:text-foreground">
            Install CLI
          </a>
        </div>
      </footer>
    </div>
  )
}
