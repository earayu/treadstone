import { createBrowserRouter, RouterProvider, Link } from "react-router"

import { PublicLayout } from "@/components/layout/public-layout"
import { AuthLayout } from "@/components/layout/auth-layout"
import { AppLayout } from "@/components/layout/app-layout"
import { AdminLayout } from "@/components/layout/admin-layout"

import { LandingPage } from "@/pages/public/landing"
import { DocsPage } from "@/pages/public/docs"

import { SignInPage } from "@/pages/auth/sign-in"
import { SignUpPage } from "@/pages/auth/sign-up"
import { ForgotPasswordPage } from "@/pages/auth/forgot-password"
import { ResetPasswordPage } from "@/pages/auth/reset-password"
import { VerifyEmailPage } from "@/pages/auth/verify-email"
import { CliLoginPage } from "@/pages/auth/cli-login"

import { SandboxesPage } from "@/pages/app/sandboxes"
import { CreateSandboxPage } from "@/pages/app/create-sandbox"
import { SandboxDetailPage } from "@/pages/app/sandbox-detail"
import { ApiKeysPage } from "@/pages/app/api-keys"
import { UsagePage } from "@/pages/app/usage"
import { SettingsPage } from "@/pages/app/settings"

import { AdminMeteringPage } from "@/pages/internal/admin-metering"
import { AdminOverviewPage } from "@/pages/internal/admin-overview"
import { AdminUsersPage } from "@/pages/internal/admin-users"
import { AdminFeedbackPage } from "@/pages/internal/admin-feedback"
import { AdminPlatformLimitsPage } from "@/pages/internal/admin-platform-limits"
import { AuditEventsPage } from "@/pages/internal/audit-events"

function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      <h1 className="text-6xl font-bold tracking-tight text-foreground">404</h1>
      <p className="mt-4 text-base text-muted-foreground">
        The page you're looking for doesn't exist.
      </p>
      <Link
        to="/"
        className="mt-8 bg-primary px-6 py-2.5 text-sm font-bold uppercase tracking-widest text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Go Home
      </Link>
    </div>
  )
}

const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      // Public docs: `/docs` (manifest default) and `/docs/:slug` only — no query-based routing.
      { path: "docs", element: <DocsPage /> },
      { path: "docs/:slug", element: <DocsPage /> },
    ],
  },
  {
    path: "auth",
    element: <AuthLayout />,
    children: [
      { path: "sign-in", element: <SignInPage /> },
      { path: "sign-up", element: <SignUpPage /> },
      { path: "forgot-password", element: <ForgotPasswordPage /> },
      { path: "reset-password", element: <ResetPasswordPage /> },
      { path: "verify-email", element: <VerifyEmailPage /> },
    ],
  },
  {
    path: "auth/cli/login",
    element: <CliLoginPage />,
  },
  {
    path: "app",
    element: <AppLayout />,
    children: [
      { index: true, element: <SandboxesPage /> },
      { path: "sandboxes/new", element: <CreateSandboxPage /> },
      { path: "sandboxes/:id", element: <SandboxDetailPage /> },
      { path: "api-keys", element: <ApiKeysPage /> },
      { path: "usage", element: <UsagePage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
  {
    path: "internal",
    element: <AdminLayout />,
    children: [
      { path: "admin/overview", element: <AdminOverviewPage /> },
      { path: "admin/users", element: <AdminUsersPage /> },
      { path: "admin/platform-limits", element: <AdminPlatformLimitsPage /> },
      { path: "admin/metering", element: <AdminMeteringPage /> },
      { path: "admin/feedback", element: <AdminFeedbackPage /> },
      { path: "audit", element: <AuditEventsPage /> },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
])

export function App() {
  return <RouterProvider router={router} />
}
