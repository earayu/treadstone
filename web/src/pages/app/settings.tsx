import { useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { HelpIcon } from "@/components/ui/help-icon"
import { client, HttpError } from "@/lib/api-client"
import { DOC } from "@/lib/console-docs"

function roleLabel(role: string): string {
  if (role === "admin") return "Admin"
  return role
}

export function SettingsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: user, isLoading } = useCurrentUser()
  const logout = useLogout()

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [changing, setChanging] = useState(false)

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!user) {
      toast.error("You must be signed in to manage your password.")
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error("New password and confirmation do not match.")
      return
    }
    if (newPassword.length < 8) {
      toast.error("New password must be at least 8 characters.")
      return
    }

    setChanging(true)
    try {
      if (user.has_local_password) {
        await client.POST("/v1/auth/change-password", {
          body: {
            old_password: currentPassword,
            new_password: newPassword,
          },
        })
      } else {
        await client.POST("/v1/auth/set-password", {
          body: {
            new_password: newPassword,
          },
        })
      }

      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      toast.success(
        user.has_local_password ? "Password updated." : "Password set. You can now sign in with email and password.",
      )
    } catch (err) {
      if (err instanceof HttpError) {
        toast.error(err.message)
      } else {
        toast.error(user.has_local_password ? "Failed to change password." : "Failed to set password.")
      }
    } finally {
      setChanging(false)
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
    <div className="mx-auto flex max-w-xl flex-col gap-10">
      <div>
        <h1 className="text-4xl font-bold tracking-tight text-foreground">Account Settings</h1>
        <p className="mt-1 flex flex-wrap items-center gap-2 text-base text-muted-foreground">
          <span>Profile and security for your account.</span>
          <HelpIcon
            content="The Console uses a browser session. For scripts and automation, create API keys instead. OAuth-only accounts can add a password here."
            link={{ href: DOC.apiKeysAuth.sessionsVsApiKeys, label: "Sessions vs API keys" }}
            side="right"
          />
        </p>
      </div>

      <section className="border border-border/15 bg-card px-6 py-6">
        <h2 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">Account</h2>
        {isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading…</p>
        ) : !user ? (
          <p className="mt-4 text-sm text-muted-foreground">Not signed in.</p>
        ) : (
          <dl className="mt-6 space-y-4">
            <div>
              <dt className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">Email</dt>
              <dd className="mt-1 text-sm text-foreground">{user.email}</dd>
            </div>
            {user.role === "admin" && (
              <div>
                <dt className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">Role</dt>
                <dd className="mt-1">
                  <span className="inline-block bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                    {roleLabel(user.role)}
                  </span>
                </dd>
              </div>
            )}
          </dl>
        )}
      </section>

      <section className="border border-border/15 bg-card px-6 py-6">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading security settings…</p>
        ) : !user ? (
          <p className="text-sm text-muted-foreground">Not signed in.</p>
        ) : (
          <>
            <h2 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
              {user.has_local_password ? "Change password" : "Set password"}
            </h2>
            {!user.has_local_password ? (
              <p className="mt-3 text-sm text-muted-foreground">
                This account currently signs in with OAuth only. Set a local password to also allow email and password
                sign-in.
              </p>
            ) : null}
            <form className="mt-6 space-y-4" onSubmit={(e) => void handlePasswordSubmit(e)}>
              {user.has_local_password ? (
                <label className="block">
                  <span className="text-xs font-semibold text-muted-foreground">Current password</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    required
                  />
                </label>
              ) : null}
              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">New password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  required
                  minLength={8}
                />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-muted-foreground">Confirm new password</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1.5 w-full border border-border/30 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  required
                  minLength={8}
                />
              </label>
              <button
                type="submit"
                disabled={changing}
                className="bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {changing
                  ? user.has_local_password
                    ? "Updating…"
                    : "Setting…"
                  : user.has_local_password
                    ? "Update password"
                    : "Set password"}
              </button>
            </form>
          </>
        )}
      </section>

      <div>
        <button
          type="button"
          onClick={() => void handleSignOut()}
          disabled={logout.isPending}
          className="border border-border/40 bg-secondary px-5 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 disabled:opacity-50"
        >
          {logout.isPending ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </div>
  )
}
