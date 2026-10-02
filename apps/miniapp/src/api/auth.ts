import { API_BASE_URL, isWeChatAuthMode } from "./config"
import { createHttpClient } from "../platform/http"
import {
  canRefreshSession,
  createSessionStore,
  createSingleFlight,
  isSessionFresh
} from "../platform/session"
import { requestWeChatLoginCode } from "../platform/wechat"

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

function isAuthSession(value: unknown): value is AuthSession {
  if (!value || typeof value !== "object") return false
  const session = value as Partial<AuthSession>
  return (
    typeof session.userId === "string" &&
    Array.isArray(session.roles) &&
    typeof session.accessToken === "string" &&
    typeof session.refreshToken === "string" &&
    typeof session.expiresAt === "number" &&
    typeof session.refreshExpiresAt === "number"
  )
}

const sessionStore = createSessionStore<AuthSession>(
  STORAGE_KEY,
  isAuthSession
)
const authFlight = createSingleFlight<AuthSession>()
const authHttp = createHttpClient({ baseUrl: API_BASE_URL })

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
  sessionStore.write(session)
  return session
}

async function rawPost<T>(
  path: string,
  data: Record<string, unknown>
): Promise<T> {
  try {
    return await authHttp.request<T>(path, {
      method: "POST",
      data
    })
  } catch (error) {
    if (error instanceof Error && error.message === "REQUEST_FAILED") {
      throw new Error("AUTH_REQUEST_FAILED")
    }
    throw error
  }
}

async function loginWithWeChat(): Promise<AuthSession> {
  const code = await requestWeChatLoginCode()
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
  return sessionStore.read()
}

export async function ensureSession(): Promise<AuthSession> {
  if (!isWeChatAuthMode()) {
    throw new Error("WECHAT_AUTH_MODE_REQUIRED")
  }

  const current = sessionStore.read()
  if (current && isSessionFresh(current, ACCESS_REFRESH_SKEW_MS)) {
    return current
  }

  return authFlight.run(async () => {
    const latest = sessionStore.read()
    if (latest && isSessionFresh(latest, ACCESS_REFRESH_SKEW_MS)) {
      return latest
    }

    if (latest && canRefreshSession(latest)) {
      try {
        return await rotateRefresh(latest)
      } catch {
        sessionStore.clear()
      }
    }
    return loginWithWeChat()
  })
}

export async function refreshSession(): Promise<AuthSession> {
  if (!isWeChatAuthMode()) {
    throw new Error("WECHAT_AUTH_MODE_REQUIRED")
  }

  return authFlight.run(async () => {
    const current = sessionStore.read()
    if (current && canRefreshSession(current)) {
      try {
        return await rotateRefresh(current)
      } catch {
        sessionStore.clear()
      }
    }
    return loginWithWeChat()
  })
}

export async function logoutSession(): Promise<void> {
  const current = sessionStore.read()
  sessionStore.clear()
  if (!current?.refreshToken || !isWeChatAuthMode()) return
  try {
    await rawPost("/auth/logout", { refreshToken: current.refreshToken })
  } catch {
    // Local logout remains authoritative for the client.
  }
}
