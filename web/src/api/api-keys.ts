import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type ApiKey = components["schemas"]["ApiKeySummary"]
export type ApiKeyCreated = components["schemas"]["ApiKeyResponse"]
export type CreateApiKeyBody = components["schemas"]["CreateApiKeyRequest"]
export type UpdateApiKeyBody = components["schemas"]["UpdateApiKeyRequest"]

export function useApiKeys() {
  return useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/auth/api-keys")
      return data!
    },
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateApiKeyBody) => {
      const { data } = await client.POST("/v1/auth/api-keys", { body })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}

export function useUpdateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: UpdateApiKeyBody }) => {
      const { data } = await client.PATCH("/v1/auth/api-keys/{key_id}", {
        params: { path: { key_id: id } },
        body,
      })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}

export function useDeleteApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.DELETE("/v1/auth/api-keys/{key_id}", {
        params: { path: { key_id: id } },
      })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  })
}
