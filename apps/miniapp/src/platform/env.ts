export type AuthMode = "demo" | "wechat"

function normalizeOrigin(value: string | undefined): string {
  const candidate = String(value || "http://localhost:8000").trim()
  return candidate.replace(/\/+$/, "")
}

export const API_ORIGIN = normalizeOrigin(import.meta.env.VITE_API_ORIGIN)
export const API_BASE_URL = API_ORIGIN + "/api/v1"

const configuredAuthMode = String(
  import.meta.env.VITE_AUTH_MODE || "demo"
).toLowerCase()

export const AUTH_MODE: AuthMode =
  configuredAuthMode === "wechat" ? "wechat" : "demo"

export const isWeChatAuthMode = () => AUTH_MODE === "wechat"

export const runtimeConfig = Object.freeze({
  apiOrigin: API_ORIGIN,
  apiBaseUrl: API_BASE_URL,
  authMode: AUTH_MODE
})
