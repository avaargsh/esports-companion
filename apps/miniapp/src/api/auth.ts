import { API_BASE_URL, isWeChatAuthMode } from "./config"
import { createHttpClient } from "../platform/http"
import { createTokenSessionAdapter } from "../platform/token-session"

const STORAGE_KEY = "esports-companion.auth.v1"
const authHttp = createHttpClient({ baseUrl: API_BASE_URL })

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

const sessionAdapter = createTokenSessionAdapter<AuthSession, AuthResponse>({
  storageKey: STORAGE_KEY,
  validate: isAuthSession,
  async login() {
    const code = await wechatLoginCode()
    return rawPost<AuthResponse>("/auth/wechat/login", { code })
  },
  refresh(session) {
    return rawPost<AuthResponse>("/auth/refresh", {
      refreshToken: session.refreshToken
    })
  },
  toSession(payload, now) {
    return {
      userId: payload.userId,
      roles: payload.roles,
      tokenType: payload.tokenType || "Bearer",
      accessToken: payload.accessToken,
      refreshToken: payload.refreshToken,
      expiresAt: now + payload.expiresIn * 1000,
      refreshExpiresAt: now + payload.refreshExpiresIn * 1000
    }
  }
})

function requireWeChatMode() {
  if (!isWeChatAuthMode()) throw new Error("WECHAT_AUTH_MODE_REQUIRED")
}

export function getStoredSession(): AuthSession | null {
  return sessionAdapter.read()
}

export async function ensureSession(): Promise<AuthSession> {
  requireWeChatMode()
  return sessionAdapter.ensure()
}

export async function refreshSession(): Promise<AuthSession> {
  requireWeChatMode()
  return sessionAdapter.refresh()
}

export async function logoutSession(): Promise<void> {
  const current = sessionAdapter.read()
  sessionAdapter.clear()
  if (!current?.refreshToken || !isWeChatAuthMode()) return
  try {
    await rawPost("/auth/logout", { refreshToken: current.refreshToken })
  } catch {
    // Local logout remains authoritative for the client.
  }
}
