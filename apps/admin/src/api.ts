const API_BASE = "/api/v1"

type Method = "GET" | "POST" | "PATCH" | "DELETE"

type DemoIdentities = {
  admin: { userId: string; nickname: string } | null
}

let adminId = ""

async function resolveAdminId() {
  if (adminId) return adminId
  const response = await fetch(API_BASE + "/dev/demo-identities")
  if (!response.ok) throw new Error("DEMO_IDENTITIES_UNAVAILABLE")
  const payload = (await response.json()) as DemoIdentities
  if (!payload.admin?.userId) throw new Error("DEMO_ADMIN_NOT_FOUND")
  adminId = payload.admin.userId
  return adminId
}

export async function adminRequest<T>(
  path: string,
  options: { method?: Method; body?: unknown } = {}
): Promise<T> {
  const id = await resolveAdminId()
  const response = await fetch(API_BASE + path, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Id": id
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  })

  if (!response.ok) {
    let detail = "REQUEST_FAILED"
    try {
      const payload = await response.json()
      detail = String(payload.detail ?? detail)
    } catch {
      // Keep generic error.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}
