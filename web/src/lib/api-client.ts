interface ApiError {
  error: {
    code: string
    message: string
    status: number
  }
}

class ApiClient {
  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    })

    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as ApiError | null
      const message = body?.error?.message ?? `Request failed: ${res.status}`
      throw new HttpError(res.status, body?.error?.code ?? "unknown", message)
    }

    if (res.status === 204) return undefined as T
    return res.json() as Promise<T>
  }

  get<T>(path: string, init?: RequestInit) {
    return this.request<T>(path, { ...init, method: "GET" })
  }

  post<T>(path: string, body?: unknown, init?: RequestInit) {
    return this.request<T>(path, {
      ...init,
      method: "POST",
      body: body != null ? JSON.stringify(body) : undefined,
    })
  }

  put<T>(path: string, body?: unknown, init?: RequestInit) {
    return this.request<T>(path, {
      ...init,
      method: "PUT",
      body: body != null ? JSON.stringify(body) : undefined,
    })
  }

  patch<T>(path: string, body?: unknown, init?: RequestInit) {
    return this.request<T>(path, {
      ...init,
      method: "PATCH",
      body: body != null ? JSON.stringify(body) : undefined,
    })
  }

  delete<T>(path: string, init?: RequestInit) {
    return this.request<T>(path, { ...init, method: "DELETE" })
  }
}

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

export const api = new ApiClient()
