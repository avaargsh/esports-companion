import { API_ORIGIN } from "./config"
import { createHttpClient } from "../platform/http"
import { getStoredSession } from "./auth"

export type ApiEnvelope<T> = {
  code: number
  message: string
  data: T
}

export type WxLoginData = {
  userId: string
  openid: string
  tokenType: string
  token: string
  accessToken: string
  refreshToken: string
  expiresIn: number
  refreshExpiresIn: number
  roles: string[]
  nickname?: string
  avatarUrl?: string | null
  phone?: string | null
}

export type BindPhoneData = {
  phone: string
  bound: boolean
}

export type CurrentUserProfile = {
  userId: string
  openid?: string | null
  nickname: string
  avatarUrl?: string | null
  phone?: string | null
  role: string
  status: string
}

export type AvatarUploadData = {
  key: string
  url: string
}

const userHttp = createHttpClient({ baseUrl: API_ORIGIN })
const STORAGE_KEY = "esports-companion.auth.v1"

function persistLogin(data: WxLoginData) {
  const now = Date.now()
  uni.setStorageSync(STORAGE_KEY, {
    userId: data.userId,
    roles: data.roles,
    tokenType: data.tokenType || "Bearer",
    accessToken: data.accessToken || data.token,
    refreshToken: data.refreshToken,
    expiresAt: now + data.expiresIn * 1000,
    refreshExpiresAt: now + data.refreshExpiresIn * 1000
  })
}

function unwrap<T>(payload: ApiEnvelope<T>): T {
  if (payload.code !== 0) throw new Error(payload.message || "REQUEST_FAILED")
  return payload.data
}

function authHeaders(): Record<string, string> {
  const session = getStoredSession()
  if (!session?.accessToken) throw new Error("LOGIN_REQUIRED")
  return {
    Authorization: `${session.tokenType || "Bearer"} ${session.accessToken}`
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

export async function wxUserLogin(): Promise<WxLoginData> {
  const code = await wechatLoginCode()
  const payload = await userHttp.request<ApiEnvelope<WxLoginData>>(
    "/api/user/wx-login",
    { method: "POST", data: { code } }
  )
  const data = unwrap(payload)
  persistLogin(data)
  return data
}

export async function getCurrentUserProfile(): Promise<CurrentUserProfile> {
  const payload = await userHttp.request<ApiEnvelope<CurrentUserProfile>>("/api/user/me", {
    headers: authHeaders()
  })
  return unwrap(payload)
}

export async function updateCurrentUserProfile(data: {
  nickname?: string
  avatarUrl?: string | null
}): Promise<CurrentUserProfile> {
  const payload = await userHttp.request<ApiEnvelope<CurrentUserProfile>>("/api/user/profile", {
    method: "POST",
    data,
    headers: authHeaders()
  })
  return unwrap(payload)
}

export async function uploadUserAvatar(data: {
  filename: string
  contentType: string
  dataBase64: string
}): Promise<AvatarUploadData> {
  const payload = await userHttp.request<ApiEnvelope<AvatarUploadData>>("/api/user/avatar", {
    method: "POST",
    data,
    headers: authHeaders()
  })
  return unwrap(payload)
}

export async function bindPhoneNumber(detail: {
  encryptedData?: string
  iv?: string
}): Promise<BindPhoneData> {
  if (!detail.encryptedData || !detail.iv) {
    throw new Error("PHONE_AUTH_CANCELED")
  }
  const session = getStoredSession()
  if (!session?.accessToken) {
    throw new Error("LOGIN_REQUIRED")
  }
  const payload = await userHttp.request<ApiEnvelope<BindPhoneData>>(
    "/api/user/bind-phone",
    {
      method: "POST",
      data: {
        encryptedData: detail.encryptedData,
        iv: detail.iv
      },
      headers: {
        Authorization: `${session.tokenType || "Bearer"} ${session.accessToken}`
      }
    }
  )
  return unwrap(payload)
}
