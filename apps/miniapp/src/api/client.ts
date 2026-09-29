export const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN || "http://localhost:8000"
export const API_BASE_URL = API_ORIGIN + "/api/v1"

type Method = "GET" | "POST" | "PATCH" | "DELETE"

export async function request<T>(
  path: string,
  options: {
    method?: Method
    data?: UniApp.RequestOptions["data"]
    userId?: string
    adminId?: string
    headers?: Record<string, string>
  } = {}
): Promise<T> {
  const response = await uni.request({
    url: API_BASE_URL + path,
    method: (options.method ?? "GET") as UniApp.RequestOptions["method"],
    data: options.data,
    header: {
      "Content-Type": "application/json",
      ...(options.userId ? { "X-User-Id": options.userId } : {}),
      ...(options.adminId ? { "X-Admin-Id": options.adminId } : {}),
      ...(options.headers ?? {})
    }
  })

  if (response.statusCode < 200 || response.statusCode >= 300) {
    const message =
      typeof response.data === "object" && response.data && "detail" in response.data
        ? String((response.data as { detail: unknown }).detail)
        : "REQUEST_FAILED"
    throw new Error(message)
  }

  return response.data as T
}
