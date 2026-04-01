import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import type { components } from "@/api/schema"
import { client } from "@/lib/api-client"

export type Sandbox = components["schemas"]["SandboxResponse"]
export type CreateSandboxBody = components["schemas"]["CreateSandboxRequest"]

const TRANSITIONING_STATUSES = new Set(["creating", "starting", "stopping", "deleting"])

export function useSandboxes() {
  return useQuery({
    queryKey: ["sandboxes"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/sandboxes")
      return data!
    },
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 30_000
      const hasTransitioning = data.items?.some((s) => TRANSITIONING_STATUSES.has(s.status))
      return hasTransitioning ? 5_000 : 30_000
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
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 30_000
      return TRANSITIONING_STATUSES.has(data.status) ? 5_000 : 30_000
    },
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

export function useUpdateSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: string
      body: components["schemas"]["UpdateSandboxRequest"]
    }) => {
      const { data } = await client.PATCH("/v1/sandboxes/{sandbox_id}", {
        params: { path: { sandbox_id: id } },
        body,
      })
      return data!
    },
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: ["sandboxes"] })
      void qc.invalidateQueries({ queryKey: ["sandboxes", vars.id] })
    },
  })
}
