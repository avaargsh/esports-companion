import { ensureSession, refreshSession } from "./auth"
import { API_BASE_URL, API_ORIGIN, isWeChatAuthMode } from "./config"
import {
  createHttpClient,
  type HttpMethod
} from "../platform/http"

export { API_BASE_URL, API_ORIGIN } from "./config"

type RequestOptions = {
  method?: HttpMethod
  data?: string | Record<string, unknown> | ArrayBuffer
  userId?: string
  adminId?: string
  headers?: Record<string, string>
}

const http = createHttpClient({
  baseUrl: API_BASE_URL,
  auth: {
    async getHeaders() {
      const session = await ensureSession()
      return {
        Authorization:
          `${session.tokenType || "Bearer"} ${session.accessToken}`
      }
    },
    async refresh() {
      await refreshSession()
    }
  }
})

export async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const requiresIdentity = Boolean(options.userId || options.adminId)
  const headers: Record<string, string> = {
    ...(options.headers ?? {})
  }

  if (!isWeChatAuthMode()) {
    if (options.userId) headers["X-User-Id"] = options.userId
    if (options.adminId) headers["X-Admin-Id"] = options.adminId
  }

  return http.request<T>(path, {
    method: options.method,
    data: options.data,
    headers,
    auth: requiresIdentity && isWeChatAuthMode()
  })
}
