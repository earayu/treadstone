import createClient, { type Middleware } from "openapi-fetch"
import type { paths } from "@/api/schema"

export class HttpError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "HttpError"
    this.status = status
    this.code = code
  }
}

const errorMiddleware: Middleware = {
  async onResponse({ response }) {
    if (response.ok || response.status === 204) return undefined

    const body = await response.clone().json().catch(() => null) as {
      error?: { code?: string; message?: string; status?: number }
    } | null

    throw new HttpError(
      response.status,
      body?.error?.code ?? "unknown",
      body?.error?.message ?? `Request failed: ${response.status}`,
    )
  },
}

export const client = createClient<paths>({
  credentials: "include",
})

client.use(errorMiddleware)
