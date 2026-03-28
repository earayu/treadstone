import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type TierTemplate = components["schemas"]["TierTemplateItem"]
export type UsageSummary = components["schemas"]["UsageSummaryResponse"]

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

export function useAdminCreateGrant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      body,
    }: {
      userId: string
      body: components["schemas"]["CreateGrantRequest"]
    }) => {
      const { data } = await client.POST("/v1/admin/users/{user_id}/grants", {
        params: { path: { user_id: userId } },
        body,
      })
      return data!
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["admin", "user-usage", vars.userId] }),
  })
}

export function useAdminBatchGrants() {
  return useMutation({
    mutationFn: async (body: components["schemas"]["BatchGrantRequest"]) => {
      const { data } = await client.POST("/v1/admin/grants/batch", { body })
      return data!
    },
  })
}
