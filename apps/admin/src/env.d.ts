/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_ADMIN_AUTH_MODE?: "demo" | "bearer"
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
