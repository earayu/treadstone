import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api-client"

export interface UsageOverview {
  tier: string
  billing_period_start: string
  billing_period_end: string
  compute_credits_monthly: number
  compute_credits_used: number
  compute_credits_remaining: number
  extra_credits_remaining: number
  total_credits_remaining: number
  storage_quota_bytes: number
  current_running_count: number
  max_concurrent_running: number
  max_sandbox_duration_seconds: number
}

export interface ComputeSession {
  id: string
  sandbox_id: string
  template: string
  credit_rate_per_hour: number
  duration_seconds: number
  credits_consumed: number
  status: string
  started_at: string
  ended_at: string | null
}

export interface CreditGrant {
  id: string
  credit_type: string
  grant_type: string
  original_amount: number
  remaining_amount: number
  status: string
  expires_at: string | null
  created_at: string
}

export function useUsageOverview() {
  return useQuery<UsageOverview>({
    queryKey: ["usage", "overview"],
    queryFn: () => api.get<UsageOverview>("/v1/usage/overview"),
  })
}

export function useComputeSessions() {
  return useQuery<ComputeSession[]>({
    queryKey: ["usage", "sessions"],
    queryFn: () => api.get<ComputeSession[]>("/v1/usage/sessions"),
  })
}

export function useCreditGrants() {
  return useQuery<CreditGrant[]>({
    queryKey: ["usage", "grants"],
    queryFn: () => api.get<CreditGrant[]>("/v1/usage/grants"),
  })
}
