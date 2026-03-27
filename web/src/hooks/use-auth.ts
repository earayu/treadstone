import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { client, HttpError } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type User = components["schemas"]["UserDetailResponse"]

export function useCurrentUser() {
  return useQuery<User | null>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        const { data } = await client.GET("/v1/auth/user")
        return data ?? null
      } catch (e) {
        if (e instanceof HttpError && e.status === 401) return null
        throw e
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      const { data } = await client.POST("/v1/auth/login", { body })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await client.POST("/v1/auth/logout")
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) => {
      const { data } = await client.POST("/v1/auth/register", { body })
      return data!
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}
