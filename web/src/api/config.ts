import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api-client"

export interface AppConfig {
  auth_type: string
  google_oauth_enabled: boolean
  github_oauth_enabled: boolean
}

export function useAppConfig() {
  return useQuery<AppConfig>({
    queryKey: ["config"],
    queryFn: () => api.get<AppConfig>("/v1/config"),
    staleTime: 10 * 60 * 1000,
  })
}
