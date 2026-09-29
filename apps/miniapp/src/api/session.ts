const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN || "http://localhost:8000"
const API_BASE_URL = API_ORIGIN + "/api/v1"
const STORAGE_KEY = "esports-companion:auth-session"

export type AppSession = {
  userId: string
  roles: string[]
  accessToken: string
  refreshToken: string
  expiresAt: number
  refreshExpiresAt: number
}

type LoginPayload = {
  userId: string
  roles: string[]
  accessToken: string
  refreshToken: string
  expiresIn: number
  refreshExpiresIn: number
}

export const AUTH_MODE =
  (import.meta.env.VITE_AUTH_MODE || (import.meta.env.PROD ? "wechat" : "demo"))
    .trim()
    .toLowerCase()

let sessionFlight: Promise<AppSession> | null = null

export function usesWechatSession(): boolean {
  return AUTH_MODE === "wechat"
}

export function readSession(): AppSession | null {
  try {
    const value = uni.getStorageSync(STORAGE_KEY)
    if (!value || typeof value !== "object") return null
    const session = value as AppSession
    if (!session.accessToken || !session.refreshToken || !session.userId) {
      return null
    }
    return session
  } catch {
    return null
  }
}

export function clearSession(): void {
  try {
    uni.removeStorageSync(STORAGE_KEY)
  } catch {
    // Storage cleanup is best-effort.
  }
}

function persist(payload: LoginPayload): AppSession {
  const now = Date.now()
  const session: AppSession = {
    userId: payload.userId,
    roles: payload.roles,
    accessToken: payload.accessToken,
    refreshToken: payload.refreshToken,
    expiresAt: now + payload.expiresIn * 1000,
    refreshExpiresAt: now + payload.refreshExpiresIn * 1000
  }
  uni.setStorageSync(STORAGE_KEY, session)
  return session
}

async function postAuth<T>(
  path: string,
  data: Record<string, unknown>
): Promise<T> {
  const response = await uni.request({
    url: API_BASE_URL + path,
    method: "POST",
    data,
    header: { "Content-Type": "application/json" }
  })
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const message =
      typeof response.data === "object" &&
      response.data &&
      "detail" in response.data
        ? String((response.data as { detail: unknown }).detail)
        : "AUTH_REQUEST_FAILED"
    throw new Error(message)
  }
  return response.data as T
}

function requestWeChatCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success(result) {
        if (result.code) {
          resolve(result.code)
          return
        }
        reject(new Error("WECHAT_LOGIN_CODE_MISSING"))
      },
      fail() {
        reject(new Error("WECHAT_LOGIN_FAILED"))
      }
    })
  })
}

export async function loginWechat(): Promise<AppSession> {
  const code = await requestWeChatCode()
  const payload = await postAuth<LoginPayload>("/auth/wechat/login", { code })
  return persist(payload)
}

export async function refreshWechatSession(): Promise<AppSession> {
  const current = readSession()
  if (!current?.refreshToken || current.refreshExpiresAt <= Date.now()) {
    clearSession()
    throw new Error("REFRESH_SESSION_UNAVAILABLE")
  }
  const payload = await postAuth<LoginPayload>("/auth/refresh", {
    refreshToken: current.refreshToken
  })
  return persist(payload)
}

export async function ensureSession(): Promise<AppSession> {
  if (!usesWechatSession()) {
    throw new Error("WECHAT_SESSION_DISABLED")
  }

  const current = readSession()
  if (current && current.expiresAt > Date.now() + 30_000) {
    return current
  }

  if (!sessionFlight) {
    sessionFlight = (async () => {
      if (current?.refreshToken && current.refreshExpiresAt > Date.now()) {
        try {
          return await refreshWechatSession()
        } catch {
          clearSession()
        }
      }
      return loginWechat()
    })().finally(() => {
      sessionFlight = null
    })
  }
  return sessionFlight
}

export function websocketAuth(userId: string): {
  query: string
  header?: Record<string, string>
} {
  if (!usesWechatSession()) {
    return {
      query: `?user_id=${encodeURIComponent(userId)}`
    }
  }
  const session = readSession()
  return {
    query: "",
    header: session?.accessToken
      ? { Authorization: `Bearer ${session.accessToken}` }
      : undefined
  }
}
