import { API_BASE_URL, isWeChatAuthMode } from "./config"

const STORAGE_KEY = "esports-companion.auth.v1"
const ACCESS_REFRESH_SKEW_MS = 30_000

type AuthResponse = {
  userId: string
  roles: string[]
  tokenType: string
  accessToken: string
  refreshToken: string
  expiresIn: number
  refreshExpiresIn: number
}

export type AuthSession = {
  userId: string
  roles: string[]
  tokenType: string
  accessToken: string
  refreshToken: string
  expiresAt: number
  refreshExpiresAt: number
}

let authTask: Promise<AuthSession> | null = null

function readSession(): AuthSession | null {
  const value = uni.getStorageSync(STORAGE_KEY)
  if (!value || typeof value !== "object") return null
  const session = value as Partial<AuthSession>
  if (
    typeof session.userId !== "string" ||
    !Array.isArray(session.roles) ||
    typeof session.accessToken !== "string" ||
    typeof session.refreshToken !== "string" ||
    typeof session.expiresAt !== "number" ||
    typeof session.refreshExpiresAt !== "number"
  ) {
    return null
  }
  return session as AuthSession
}

function persistSession(payload: AuthResponse): AuthSession {
  const now = Date.now()
  const session: AuthSession = {
    userId: payload.userId,
    roles: payload.roles,
    tokenType: payload.tokenType || "Bearer",
    accessToken: payload.accessToken,
    refreshToken: payload.refreshToken,
    expiresAt: now + payload.expiresIn * 1000,
    refreshExpiresAt: now + payload.refreshExpiresIn * 1000
  }
  uni.setStorageSync(STORAGE_KEY, session)
  return session
}

function clearStoredSession() {
  uni.removeStorageSync(STORAGE_KEY)
}

function runExclusive(task: () => Promise<AuthSession>): Promise<AuthSession> {
  if (authTask) return authTask
  authTask = task().finally(() => {
    authTask = null
  })
  return authTask
}

async function rawPost<T>(
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
    const detail =
      typeof response.data === "object" &&
      response.data &&
      "detail" in response.data
        ? String((response.data as { detail: unknown }).detail)
        : "AUTH_REQUEST_FAILED"
    throw new Error(detail)
  }
  return response.data as T
}

function wechatLoginCode(): Promise<string> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success(result) {
        if (result.code) resolve(result.code)
        else reject(new Error("WECHAT_LOGIN_CODE_MISSING"))
      },
      fail() {
        reject(new Error("WECHAT_LOGIN_FAILED"))
      }
    })
  })
}

async function loginWithWeChat(): Promise<AuthSession> {
  const code = await wechatLoginCode()
  const payload = await rawPost<AuthResponse>("/auth/wechat/login", { code })
  return persistSession(payload)
}

async function rotateRefresh(current: AuthSession): Promise<AuthSession> {
  const payload = await rawPost<AuthResponse>("/auth/refresh", {
    refreshToken: current.refreshToken
  })
  return persistSession(payload)
}

export function getStoredSession(): AuthSession | null {
  return readSession()
}

export async function ensureSession(): Promise<AuthSession> {
  if (!isWeChatAuthMode()) {
    throw new Error("WECHAT_AUTH_MODE_REQUIRED")
  }

  const current = readSession()
  if (current && current.expiresAt > Date.now() + ACCESS_REFRESH_SKEW_MS) {
    return current
  }

  return runExclusive(async () => {
    const latest = readSession()
    if (latest && latest.expiresAt > Date.now() + ACCESS_REFRESH_SKEW_MS) {
      return latest
    }

    if (latest && latest.refreshExpiresAt > Date.now()) {
      try {
        return await rotateRefresh(latest)
      } catch {
        clearStoredSession()
      }
    }
    return loginWithWeChat()
  })
}

export async function refreshSession(): Promise<AuthSession> {
  if (!isWeChatAuthMode()) {
    throw new Error("WECHAT_AUTH_MODE_REQUIRED")
  }

  return runExclusive(async () => {
    const current = readSession()
    if (current && current.refreshExpiresAt > Date.now()) {
      try {
        return await rotateRefresh(current)
      } catch {
        clearStoredSession()
      }
    }
    return loginWithWeChat()
  })
}

export async function logoutSession(): Promise<void> {
  const current = readSession()
  clearStoredSession()
  if (!current?.refreshToken || !isWeChatAuthMode()) return
  try {
    await rawPost("/auth/logout", { refreshToken: current.refreshToken })
  } catch {
    // Local logout remains authoritative for the client.
  }
}
