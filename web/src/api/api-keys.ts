import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { DataPlaneMode } from "@/lib/constants"

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  created_at: string
  updated_at: string
  expires_at: string | null
  scope: {
    control_plane: boolean
    data_plane: {
      mode: DataPlaneMode
      sandbox_ids: string[]
    }
  }
}

export interface ApiKeyCreated extends ApiKey {
  key: string
}

export interface CreateApiKeyBody {
  name: string
  expires_at?: string | null
  scope?: {
    control_plane?: boolean
    data_plane?: {
      mode?: DataPlaneMode
      sandbox_ids?: string[]
    }
  }
}

export function useApiKeys() {
  return useQuery<ApiKey[]>({
    queryKey: ["api-keys"],
    queryFn: () => api.get<ApiKey[]>("/v1/auth/api-keys"),
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateApiKeyBody) =>
      api.post<ApiKeyCreated>("/v1/auth/api-keys", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}

export function useDeleteApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/v1/auth/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}
