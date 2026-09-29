import { ensureSession, refreshSession } from "./auth"
import { API_BASE_URL, API_ORIGIN, isWeChatAuthMode } from "./config"

export { API_BASE_URL, API_ORIGIN } from "./config"

type Method = "GET" | "POST" | "PUT" | "DELETE"

type RequestOptions = {
  method?: Method
  data?: string | Record<string, unknown> | ArrayBuffer
  userId?: string
  adminId?: string
  headers?: Record<string, string>
}

async function execute<T>(
  path: string,
  options: RequestOptions,
  *,
  retryAuth: boolean
): Promise<T> {
  const requiresIdentity = Boolean(options.userId || options.adminId)
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers ?? {})
  }

  if (requiresIdentity && isWeChatAuthMode()) {
    const session = await ensureSession()
    headers.Authorization =
      `${session.tokenType || "Bearer"} ${session.accessToken}`
  } else {
    if (options.userId) headers["X-User-Id"] = options.userId
    if (options.adminId) headers["X-Admin-Id"] = options.adminId
  }

  const response = await uni.request({
    url: API_BASE_URL + path,
    method: options.method ?? "GET",
    data: options.data,
    header: headers
  })

  if (
    response.statusCode === 401 &&
    requiresIdentity &&
    isWeChatAuthMode() &&
    retryAuth
  ) {
    await refreshSession()
    return execute<T>(path, options, { retryAuth: false })
  }

  if (response.statusCode < 200 || response.statusCode >= 300) {
    const message =
      typeof response.data === "object" && response.data && "detail" in response.data
        ? String((response.data as { detail: unknown }).detail)
        : "REQUEST_FAILED"
    throw new Error(message)
  }

  return response.data as T
}

export async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  return execute<T>(path, options, { retryAuth: true })
}
