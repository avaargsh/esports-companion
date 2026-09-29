const API_ORIGIN = import.meta.env.VITE_API_ORIGIN || "http://localhost:8000"
const API_BASE = API_ORIGIN + "/api/v1"

type Method = "GET" | "POST" | "PATCH" | "DELETE"

export async function api<T>(
  path: string,
  options: {
    method?: Method
    adminId?: string
    body?: unknown
  } = {}
): Promise<T> {
  const response = await fetch(API_BASE + path, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.adminId ? { "X-Admin-Id": options.adminId } : {})
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail || "REQUEST_FAILED")
  }
  return response.json()
}

export type DemoIdentities = {
  customer: { userId: string; nickname: string }
  players: Array<{ userId: string; playerId: string; displayName: string }>
  admin: { userId: string; nickname: string } | null
}
