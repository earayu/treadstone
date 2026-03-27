import { useQuery } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type SandboxTemplate = components["schemas"]["SandboxTemplateResponse"]

export function useSandboxTemplates() {
  return useQuery({
    queryKey: ["sandbox-templates"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/sandbox-templates")
      return data!
    },
    staleTime: 5 * 60 * 1000,
  })
}
