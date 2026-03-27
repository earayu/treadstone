import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api-client"

export interface SandboxTemplate {
  name: string
  display_name: string
  cpu: string
  memory: string
  description: string
}

export function useSandboxTemplates() {
  return useQuery<SandboxTemplate[]>({
    queryKey: ["sandbox-templates"],
    queryFn: () => api.get<SandboxTemplate[]>("/v1/sandbox-templates"),
    staleTime: 5 * 60 * 1000,
  })
}
