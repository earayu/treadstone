import { useQuery } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type AppConfig = components["schemas"]["ConfigResponse"]

export function useAppConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/config")
      return data!
    },
    staleTime: 10 * 60 * 1000,
  })
}
