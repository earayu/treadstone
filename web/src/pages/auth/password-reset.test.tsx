import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { createMemoryRouter, RouterProvider } from "react-router"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { SignInPage } from "@/pages/auth/sign-in"
import { ForgotPasswordPage } from "@/pages/auth/forgot-password"
import { ResetPasswordPage } from "@/pages/auth/reset-password"

vi.mock("@/api/config", () => ({
  useAppConfig: () => ({
    data: { auth: { login_methods: ["email"] } },
    isLoading: false,
  }),
}))

vi.mock("@/hooks/use-auth", () => ({
  useCurrentUser: () => ({ data: null, isLoading: false }),
  useLogin: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function renderWithRouter(initialEntry: string, routes: { path: string; element: ReactNode }[]) {
  const router = createMemoryRouter(routes, { initialEntries: [initialEntry] })
  return { router, ...render(<RouterProvider router={router} />) }
}

describe("password reset pages", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    cleanup()
  })

  it("shows a forgot password link on the sign-in page", () => {
    renderWithRouter("/auth/sign-in", [{ path: "/auth/sign-in", element: <SignInPage /> }])

    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/auth/forgot-password")
  })

  it("submits forgot-password email and shows the generic success message", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "If an account exists, we sent a password reset link." }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )

    renderWithRouter("/auth/forgot-password", [{ path: "/auth/forgot-password", element: <ForgotPasswordPage /> }])

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } })
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }))

    expect(await screen.findByText("If an account exists, we sent a password reset link.")).toBeInTheDocument()
  })

  it("shows a rate limit error on the forgot-password page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "password_reset_rate_limited", message: "Please wait 60 seconds." } }), {
        status: 429,
        headers: { "Content-Type": "application/json" },
      }),
    )

    renderWithRouter("/auth/forgot-password", [{ path: "/auth/forgot-password", element: <ForgotPasswordPage /> }])

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "user@example.com" } })
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }))

    expect(await screen.findByText("Please wait 60 seconds.")).toBeInTheDocument()
  })

  it("shows an error when reset-password token is missing", () => {
    renderWithRouter("/auth/reset-password", [{ path: "/auth/reset-password", element: <ResetPasswordPage /> }])

    expect(screen.getByText("No password reset token found. Please use the link from your email.")).toBeInTheDocument()
  })

  it("submits a new password and redirects back to sign-in", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "Password reset successful" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    )

    const { router } = renderWithRouter("/auth/reset-password?token=test-token", [
      { path: "/auth/sign-in", element: <div>sign-in target</div> },
      { path: "/auth/reset-password", element: <ResetPasswordPage /> },
    ])

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "BetterPass123!" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "BetterPass123!" } })
    fireEvent.click(screen.getByRole("button", { name: "Reset password" }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/auth/sign-in")
    })
  })

  it("shows an invalid-token error on the reset-password page", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "password_reset_token_invalid", message: "Invalid or expired password reset token." } }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    )

    renderWithRouter("/auth/reset-password?token=bad-token", [{ path: "/auth/reset-password", element: <ResetPasswordPage /> }])

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "BetterPass123!" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "BetterPass123!" } })
    fireEvent.click(screen.getByRole("button", { name: "Reset password" }))

    expect(await screen.findByText("Invalid or expired password reset token.")).toBeInTheDocument()
  })
})
