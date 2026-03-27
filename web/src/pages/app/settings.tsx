import { useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { useCurrentUser, useLogout } from "@/hooks/use-auth"
import { client, HttpError } from "@/lib/api-client"
import { cn } from "@/lib/utils"

function roleLabel(role: string): string {
  if (role === "admin") return "Admin"
  if (role === "rw") return "Member"
  if (role === "ro") return "Read only"
  return role
}

export function SettingsPage() {
  const navigate = useNavigate()
  const { data: user, isLoading } = useCurrentUser()
  const logout = useLogout()

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [changing, setChanging] = useState(false)

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
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
      await client.POST("/v1/auth/change-password", {
        body: {
          old_password: currentPassword,
          new_password: newPassword,
        },
      })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      toast.success("Password updated.")
    } catch (err) {
      if (err instanceof HttpError) {
        toast.error(err.message)
      } else {
        toast.error("Failed to change password.")
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
        <p className="mt-1 text-base text-muted-foreground">Profile and security for your account.</p>
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
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <dt className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">Role</dt>
                <dd className="mt-1">
                  <span
                    className={cn(
                      "inline-block bg-primary/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary",
                    )}
                  >
                    {roleLabel(user.role)}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">Status</dt>
                <dd className="mt-1">
                  <span className="text-sm text-success">Active</span>
                </dd>
              </div>
            </div>
          </dl>
        )}
      </section>

      <section className="border border-border/15 bg-card px-6 py-6">
        <h2 className="text-xs font-bold uppercase tracking-[1.2px] text-muted-foreground">
          Change password
        </h2>
        <form className="mt-6 space-y-4" onSubmit={(e) => void handleChangePassword(e)}>
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
            {changing ? "Updating…" : "Update password"}
          </button>
        </form>
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
