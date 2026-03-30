import { useEffect, useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

/** Page size for admin user list (must match `GET /v1/auth/users` pagination). */
export const ADMIN_USERS_PAGE_SIZE = 20

export type TierTemplate = components["schemas"]["TierTemplateItem"]
export type UsageSummary = components["schemas"]["UsageSummaryResponse"]
export type UserItem = components["schemas"]["UserResponse"]
export type PlatformStats = components["schemas"]["PlatformStatsResponse"]

export function usePlatformStats() {
  return useQuery({
    queryKey: ["admin", "platform-stats"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/admin/stats")
      return data!
    },
  })
}

export function useTierTemplates() {
  return useQuery({
    queryKey: ["admin", "tier-templates"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/admin/tier-templates")
      return data!
    },
  })
}

export function useUpdateTierTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      tierName,
      body,
    }: {
      tierName: string
      body: components["schemas"]["UpdateTierTemplateRequest"]
    }) => {
      const { data } = await client.PATCH("/v1/admin/tier-templates/{tier_name}", {
        params: { path: { tier_name: tierName } },
        body,
      })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "tier-templates"] }),
  })
}

export function useLookupUserByEmail() {
  return useMutation({
    mutationFn: async (email: string) => {
      const { data } = await client.GET("/v1/admin/users/lookup-by-email", {
        params: { query: { email } },
      })
      return data!
    },
  })
}

export function useResolveEmails() {
  return useMutation({
    mutationFn: async (emails: string[]) => {
      const { data } = await client.POST("/v1/admin/users/resolve-emails", {
        body: { emails },
      })
      return data!
    },
  })
}

export function useAdminUserUsage(userId: string | null) {
  return useQuery({
    queryKey: ["admin", "user-usage", userId],
    queryFn: async () => {
      const { data } = await client.GET("/v1/admin/users/{user_id}/usage", {
        params: { path: { user_id: userId! } },
      })
      return data!
    },
    enabled: !!userId,
  })
}

export function useAdminUpdatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string
      body: components["schemas"]["UpdatePlanRequest"]
    }) => {
      const { data } = await client.PATCH("/v1/admin/users/{user_id}/plan", {
        params: { path: { user_id: userId } },
        body,
      })
      return data!
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["admin", "user-usage", vars.userId] }),
  })
}

export function useAdminCreateComputeGrant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string
      body: components["schemas"]["CreateComputeGrantRequest"]
    }) => {
      const { data } = await client.POST("/v1/admin/users/{user_id}/compute-grants", {
        params: { path: { user_id: userId } },
        body,
      })
      return data!
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["admin", "user-usage", vars.userId] }),
  })
}

export function useAdminCreateStorageGrant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string
      body: components["schemas"]["CreateStorageQuotaGrantRequest"]
    }) => {
      const { data } = await client.POST("/v1/admin/users/{user_id}/storage-grants", {
        params: { path: { user_id: userId } },
        body,
      })
      return data!
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["admin", "user-usage", vars.userId] }),
  })
}

export function useAdminBatchComputeGrants() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["BatchComputeGrantRequest"]) => {
      const { data } = await client.POST("/v1/admin/compute-grants/batch", { body })
      return data!
    },
  })
}

export function useAdminBatchStorageGrants() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["BatchStorageQuotaGrantRequest"]) => {
      const { data } = await client.POST("/v1/admin/storage-grants/batch", { body })
      return data!
    },
  })
}

export function useAdminListUsers(params: { page: number; email?: string }) {
  return useQuery({
    queryKey: ["admin", "users", params.page, ADMIN_USERS_PAGE_SIZE, params.email ?? ""],
    queryFn: async () => {
      const { data } = await client.GET("/v1/auth/users", {
        params: {
          query: {
            limit: ADMIN_USERS_PAGE_SIZE,
            offset: params.page * ADMIN_USERS_PAGE_SIZE,
            ...(params.email ? { email: params.email } : {}),
          },
        },
      })
      return data!
    },
  })
}

/** Debounced email filter + page state for the admin users table. */
export function useAdminUsersListState() {
  const [page, setPage] = useState(0)
  const [emailInput, setEmailInput] = useState("")
  const [debouncedEmail, setDebouncedEmail] = useState("")

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedEmail(emailInput.trim()), 300)
    return () => window.clearTimeout(t)
  }, [emailInput])

  const list = useAdminListUsers({
    page,
    email: debouncedEmail || undefined,
  })

  return {
    ...list,
    page,
    setPage,
    emailInput,
    setEmailInput,
    debouncedEmail,
  }
}

export function useAdminUpdateUserStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ userId, isActive }: { userId: string; isActive: boolean }) => {
      const { data } = await client.PATCH("/v1/auth/users/{user_id}/status", {
        params: { path: { user_id: userId } },
        body: { is_active: isActive },
      })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  })
}
