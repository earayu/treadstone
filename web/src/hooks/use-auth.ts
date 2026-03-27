import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, HttpError } from "@/lib/api-client"

export interface User {
  id: string
  email: string
  role: string
  username: string | null
  is_active: boolean
}

export function useCurrentUser() {
  return useQuery<User | null>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await api.get<User>("/v1/auth/user")
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
    mutationFn: (body: { email: string; password: string }) =>
      api.post<User>("/v1/auth/login", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<void>("/v1/auth/logout"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<User>("/v1/auth/register", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  })
}
