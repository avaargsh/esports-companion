export type AuthMode = "demo" | "wechat"

export const API_ORIGIN =
  import.meta.env.VITE_API_ORIGIN || "http://localhost:8000"

export const API_BASE_URL = API_ORIGIN + "/api/v1"

const configuredAuthMode = String(
  import.meta.env.VITE_AUTH_MODE || "demo"
).toLowerCase()

export const AUTH_MODE: AuthMode =
  configuredAuthMode === "wechat" ? "wechat" : "demo"

export const isWeChatAuthMode = () => AUTH_MODE === "wechat"
