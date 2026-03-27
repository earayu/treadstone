import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type Sandbox = components["schemas"]["SandboxResponse"]
export type CreateSandboxBody = components["schemas"]["CreateSandboxRequest"]

export function useSandboxes() {
  return useQuery({
    queryKey: ["sandboxes"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/sandboxes")
      return data!
    },
  })
}

export function useSandbox(id: string) {
  return useQuery({
    queryKey: ["sandboxes", id],
    queryFn: async () => {
      const { data } = await client.GET("/v1/sandboxes/{sandbox_id}", {
        params: { path: { sandbox_id: id } },
      })
      return data!
    },
    enabled: !!id,
  })
}

export function useCreateSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateSandboxBody) => {
      const { data } = await client.POST("/v1/sandboxes", { body })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useDeleteSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await client.DELETE("/v1/sandboxes/{sandbox_id}", {
        params: { path: { sandbox_id: id } },
      })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useStartSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await client.POST("/v1/sandboxes/{sandbox_id}/start", {
        params: { path: { sandbox_id: id } },
      })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useStopSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await client.POST("/v1/sandboxes/{sandbox_id}/stop", {
        params: { path: { sandbox_id: id } },
      })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}
