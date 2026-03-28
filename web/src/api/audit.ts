import { useQuery } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type AuditEvent = components["schemas"]["AuditEventResponse"]

export function useAuditFilterOptions() {
  return useQuery({
    queryKey: ["audit", "filter-options"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/audit/filter-options")
      return data!
    },
  })
}

export function useAuditEvents(params?: {
  action?: string | null
  target_type?: string | null
  target_id?: string | null
  actor_user_id?: string | null
  actor_email?: string | null
  result?: string | null
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: ["audit", "events", params],
    queryFn: async () => {
      const { data } = await client.GET("/v1/audit/events", {
        params: { query: params },
      })
      return data!
    },
  })
}
