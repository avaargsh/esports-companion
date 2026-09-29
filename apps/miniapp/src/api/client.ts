import {
  clearSession,
  ensureSession,
  loginWechat,
  refreshWechatSession,
  usesWechatSession
} from "./session"

export const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN || "http://localhost:8000"
export const API_BASE_URL = API_ORIGIN + "/api/v1"

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
  accessToken?: string
): Promise<{ statusCode: number; data: T | unknown }> {
  const response = await uni.request({
    url: API_BASE_URL + path,
    method: options.method ?? "GET",
    data: options.data,
    header: {
      "Content-Type": "application/json",
      ...(!usesWechatSession() && options.userId
        ? { "X-User-Id": options.userId }
        : {}),
      ...(!usesWechatSession() && options.adminId
        ? { "X-Admin-Id": options.adminId }
        : {}),
      ...(accessToken
        ? { Authorization: `Bearer ${accessToken}` }
        : {}),
      ...(options.headers ?? {})
    }
  })
  return {
    statusCode: response.statusCode,
    data: response.data
  }
}

function errorMessage(data: unknown): string {
  return typeof data === "object" && data && "detail" in data
    ? String((data as { detail: unknown }).detail)
    : "REQUEST_FAILED"
}

export async function request<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  let accessToken: string | undefined
  if (usesWechatSession()) {
    accessToken = (await ensureSession()).accessToken
  }

  let response = await execute<T>(path, options, accessToken)

  if (
    response.statusCode === 401 &&
    usesWechatSession() &&
    !path.startsWith("/auth/")
  ) {
    try {
      accessToken = (await refreshWechatSession()).accessToken
    } catch {
      clearSession()
      accessToken = (await loginWechat()).accessToken
    }
    response = await execute<T>(path, options, accessToken)
  }

  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(errorMessage(response.data))
  }
  return response.data as T
}
