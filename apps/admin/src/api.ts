const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1"
const AUTH_MODE =
  String(import.meta.env.VITE_ADMIN_AUTH_MODE || "bearer").toLowerCase() === "bearer"
    ? "bearer"
    : "demo"

type Method = "GET" | "POST" | "PATCH" | "DELETE"

type DemoIdentities = {
  admin: { userId: string; nickname: string } | null
}

type AdminSession = {
  accessToken: string
  refreshToken?: string
}

type RefreshResponse = {
  accessToken: string
  refreshToken: string
}

export type AdminWechatQrConfig = {
  appId: string
  redirectUri: string
  state: string
  authorizeUrl: string
}

type AdminWechatLoginResponse = {
  userId: string
  roles: string[]
  tokenType: string
  accessToken: string
  refreshToken: string
}

const SESSION_KEY = "esports-companion.admin.session.v1"
let adminId = ""
let refreshTask: Promise<void> | null = null

function readSession(): AdminSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return null
  try {
    const session = JSON.parse(raw) as Partial<AdminSession>
    if (!session.accessToken || typeof session.accessToken !== "string") return null
    return {
      accessToken: session.accessToken,
      refreshToken:
        typeof session.refreshToken === "string" && session.refreshToken
          ? session.refreshToken
          : undefined
    }
  } catch {
    return null
  }
}

function writeSession(session: AdminSession) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
}

export function getAdminAuthMode() {
  return AUTH_MODE
}

export function isAdminSessionReady() {
  return AUTH_MODE === "demo" || Boolean(readSession()?.accessToken)
}

export function setAdminSession(accessToken: string, refreshToken?: string) {
  const access = accessToken.trim()
  if (!access) throw new Error("ADMIN_ACCESS_TOKEN_REQUIRED")
  writeSession({
    accessToken: access,
    refreshToken: refreshToken?.trim() || undefined
  })
}

export function clearAdminSession() {
  sessionStorage.removeItem(SESSION_KEY)
}

export async function getAdminWechatQrConfig() {
  const response = await fetch(API_BASE + "/auth/wechat/admin-qr")
  if (!response.ok) {
    let detail = "ADMIN_WECHAT_QR_UNAVAILABLE"
    try {
      const payload = await response.json()
      detail = String(payload.detail ?? detail)
    } catch {
      // Keep generic error.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<AdminWechatQrConfig>
}

export async function loginAdminWithWechatQrCode(code: string, state: string) {
  const loginCode = code.trim()
  const loginState = state.trim()
  if (!loginCode) throw new Error("WECHAT_LOGIN_CODE_REQUIRED")
  if (!loginState) throw new Error("WECHAT_QR_STATE_REQUIRED")
  const response = await fetch(API_BASE + "/auth/wechat/admin-qr-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: loginCode, state: loginState })
  })
  if (!response.ok) {
    let detail = "ADMIN_WECHAT_LOGIN_FAILED"
    try {
      const payload = await response.json()
      detail = String(payload.detail ?? detail)
    } catch {
      // Keep generic error.
    }
    throw new Error(detail)
  }
  const payload = (await response.json()) as AdminWechatLoginResponse
  if (!payload.roles.includes("PLATFORM")) throw new Error("PLATFORM_REQUIRED")
  writeSession({
    accessToken: payload.accessToken,
    refreshToken: payload.refreshToken
  })
  return payload
}

async function resolveAdminId() {
  if (adminId) return adminId
  const response = await fetch(API_BASE + "/dev/demo-identities")
  if (!response.ok) throw new Error("DEMO_IDENTITIES_UNAVAILABLE")
  const payload = (await response.json()) as DemoIdentities
  if (!payload.admin?.userId) throw new Error("DEMO_ADMIN_NOT_FOUND")
  adminId = payload.admin.userId
  return adminId
}

async function refreshBearerSession() {
  if (refreshTask) return refreshTask
  refreshTask = (async () => {
    const current = readSession()
    if (!current?.refreshToken) throw new Error("ADMIN_SESSION_EXPIRED")
    const response = await fetch(API_BASE + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: current.refreshToken })
    })
    if (!response.ok) {
      clearAdminSession()
      throw new Error("ADMIN_SESSION_EXPIRED")
    }
    const payload = (await response.json()) as RefreshResponse
    writeSession({
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken
    })
  })().finally(() => {
    refreshTask = null
  })
  return refreshTask
}

async function execute<T>(
  path: string,
  options: { method?: Method; body?: unknown },
  retryAuth: boolean
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  }

  if (AUTH_MODE === "bearer") {
    const session = readSession()
    if (!session?.accessToken) throw new Error("ADMIN_AUTH_REQUIRED")
    headers.Authorization = `Bearer ${session.accessToken}`
  } else {
    headers["X-Admin-Id"] = await resolveAdminId()
  }

  const response = await fetch(API_BASE + path, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  })

  if (response.status === 401 && AUTH_MODE === "bearer" && retryAuth) {
    await refreshBearerSession()
    return execute<T>(path, options, false)
  }

  if (!response.ok) {
    let detail = "REQUEST_FAILED"
    try {
      const payload = await response.json()
      detail = String(payload.detail ?? detail)
    } catch {
      // Keep generic error.
    }
    if (response.status === 401 && AUTH_MODE === "bearer") {
      clearAdminSession()
    }
    throw new Error(detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function adminRequest<T>(
  path: string,
  options: { method?: Method; body?: unknown } = {}
): Promise<T> {
  return execute<T>(path, options, true)
}
