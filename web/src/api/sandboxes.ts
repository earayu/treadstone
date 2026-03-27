import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api-client"
import type { SandboxStatus } from "@/lib/constants"

export interface Sandbox {
  id: string
  name: string
  template: string
  status: SandboxStatus
  labels: Record<string, string>
  auto_stop_interval: number | null
  auto_delete_interval: number | null
  persist: boolean
  storage_size: string | null
  started_at: string | null
  stopped_at: string | null
  created_at: string
}

export interface CreateSandboxBody {
  template: string
  name?: string
  labels?: Record<string, string>
  auto_stop_interval?: number
  auto_delete_interval?: number
  persist?: boolean
  storage_size?: string
}

export function useSandboxes() {
  return useQuery<Sandbox[]>({
    queryKey: ["sandboxes"],
    queryFn: () => api.get<Sandbox[]>("/v1/sandboxes"),
  })
}

export function useSandbox(id: string) {
  return useQuery<Sandbox>({
    queryKey: ["sandboxes", id],
    queryFn: () => api.get<Sandbox>(`/v1/sandboxes/${id}`),
    enabled: !!id,
  })
}

export function useCreateSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateSandboxBody) =>
      api.post<Sandbox>("/v1/sandboxes", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useDeleteSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/v1/sandboxes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useStartSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post<Sandbox>(`/v1/sandboxes/${id}/start`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}

export function useStopSandbox() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post<Sandbox>(`/v1/sandboxes/${id}/stop`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sandboxes"] }),
  })
}
