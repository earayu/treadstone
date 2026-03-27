import { useQuery } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type UsageSummary = components["schemas"]["UsageSummaryResponse"]
export type ComputeSession = components["schemas"]["ComputeSessionItem"]
export type CreditGrant = components["schemas"]["CreditGrantItem"]
export type UserPlan = components["schemas"]["UserPlanResponse"]

export function useUsageOverview() {
  return useQuery({
    queryKey: ["usage", "overview"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/usage")
      return data!
    },
  })
}

export function useUserPlan() {
  return useQuery({
    queryKey: ["usage", "plan"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/usage/plan")
      return data!
    },
  })
}

export function useComputeSessions(params?: {
  status?: string
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ["usage", "sessions", params],
    queryFn: async () => {
      const { data } = await client.GET("/v1/usage/sessions", {
        params: { query: params },
      })
      return data!
    },
  })
}

export function useCreditGrants() {
  return useQuery({
    queryKey: ["usage", "grants"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/usage/grants")
      return data!
    },
  })
}
