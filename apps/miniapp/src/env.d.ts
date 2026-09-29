/// <reference types="vite/client" />
/// <reference types="@dcloudio/types" />

interface ImportMetaEnv {
  readonly VITE_API_ORIGIN?: string
  readonly VITE_AUTH_MODE?: "demo" | "wechat"
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
