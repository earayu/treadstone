import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { client } from "@/lib/api-client"
import type { components } from "@/api/schema"

export type FeedbackItem = components["schemas"]["FeedbackItemResponse"]

export const ADMIN_FEEDBACK_PAGE_SIZE = 50

export function useSubmitFeedback() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: components["schemas"]["CreateFeedbackRequest"]) => {
      const { data, error } = await client.POST("/v1/support/feedback", { body })
      if (error) throw error
      return data!
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "support-feedback"] })
    },
  })
}

/** First page only (`offset=0`). Add a `page` argument here if the admin UI gains pagination. */
export function useAdminFeedbackList() {
  return useQuery({
    queryKey: ["admin", "support-feedback"],
    queryFn: async () => {
      const { data } = await client.GET("/v1/admin/support/feedback", {
        params: { query: { limit: ADMIN_FEEDBACK_PAGE_SIZE, offset: 0 } },
      })
      return data!
    },
  })
}
