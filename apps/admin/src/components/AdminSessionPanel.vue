<script setup lang="ts">
import { onMounted, ref } from "vue"

import {
  adminRequest,
  getAdminWechatQrConfig,
  loginAdminWithWechatQrCode,
  setAdminSession,
  type AdminWechatQrConfig
} from "../api"

const emit = defineEmits<{ ready: [] }>()
const accessToken = ref("")
const refreshToken = ref("")
const error = ref("")
const busy = ref(false)
const tokenBusy = ref(false)
const loadingQr = ref(false)
const showTokenFallback = ref(false)
const qrConfig = ref<AdminWechatQrConfig | null>(null)

function cleanCallbackQuery() {
  const url = new URL(window.location.href)
  url.searchParams.delete("code")
  url.searchParams.delete("state")
  window.history.replaceState({}, document.title, url.pathname + url.search + url.hash)
}

async function enterAdmin() {
  const me = await adminRequest<{ roles: string[] }>("/auth/me")
  if (!me.roles.includes("PLATFORM")) throw new Error("PLATFORM_REQUIRED")
  emit("ready")
}

async function loadQr() {
  loadingQr.value = true
  error.value = ""
  try {
    qrConfig.value = await getAdminWechatQrConfig()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "微信扫码登录暂不可用"
  } finally {
    loadingQr.value = false
  }
}

async function submitQrCallback(code: string, state: string) {
  if (busy.value) return
  busy.value = true
  error.value = ""
  try {
    await loginAdminWithWechatQrCode(code, state)
    cleanCallbackQuery()
    await enterAdmin()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "微信扫码登录失败"
    await loadQr()
  } finally {
    busy.value = false
  }
}

async function submitToken() {
  if (tokenBusy.value) return
  error.value = ""
  tokenBusy.value = true
  try {
    setAdminSession(accessToken.value, refreshToken.value)
    await enterAdmin()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "认证失败"
  } finally {
    tokenBusy.value = false
  }
}

onMounted(async () => {
  const params = new URLSearchParams(window.location.search)
  const code = params.get("code")
  const state = params.get("state")
  if (code && state) {
    await submitQrCallback(code, state)
    return
  }
  await loadQr()
})
</script>

<template>
  <section class="auth-card">
    <div class="auth-heading">
      <img src="https://img.icons8.com/fluency/96/weixing.png" alt="微信" />
      <div>
        <div class="auth-badge">SECURE OPERATOR SESSION</div>
        <h2>微信扫码登录</h2>
        <p>请使用已绑定 PLATFORM 权限的真实微信账号扫码，普通用户无法进入管理后台。</p>
      </div>
    </div>

    <div class="qr-shell">
      <div v-if="busy" class="qr-state">正在校验微信授权...</div>
      <div v-else-if="loadingQr" class="qr-state">正在生成登录二维码...</div>
      <iframe
        v-else-if="qrConfig"
        class="qr-frame"
        :src="qrConfig.authorizeUrl"
        title="微信扫码登录"
      ></iframe>
      <div v-else class="qr-state">二维码暂不可用</div>
    </div>

    <div class="qr-actions">
      <button class="ghost small" type="button" :disabled="loadingQr || busy" @click="loadQr">
        刷新二维码
      </button>
      <a v-if="qrConfig" class="open-link" :href="qrConfig.authorizeUrl" target="_blank" rel="noreferrer">
        新窗口打开
      </a>
    </div>

    <div v-if="error" class="auth-error">{{ error }}</div>

    <button class="ghost" type="button" @click="showTokenFallback = !showTokenFallback">
      {{ showTokenFallback ? "收起备用 Token 登录" : "使用已有 Token 登录" }}
    </button>

    <div v-if="showTokenFallback" class="fallback">
      <label>
        Access Token
        <textarea
          v-model="accessToken"
          autocomplete="off"
          spellcheck="false"
          placeholder="Bearer access token，不要包含 Bearer 前缀"
        />
      </label>
      <label>
        Refresh Token <small>可选</small>
        <input
          v-model="refreshToken"
          type="password"
          autocomplete="off"
          placeholder="用于 access token 过期后的自动刷新"
        />
      </label>
      <button class="secondary" :disabled="!accessToken.trim() || tokenBusy" @click="submitToken">
        {{ tokenBusy ? "正在校验..." : "校验 Token 并进入" }}
      </button>
    </div>

    <small class="security-note">
      扫码登录使用微信开放平台网站应用配置。回调域名必须与微信开放平台授权回调域一致，并且账号需通过 unionid 对应到本系统 PLATFORM 用户。
    </small>
  </section>
</template>

<style scoped>
.auth-card { max-width:760px; margin:56px auto; padding:34px; border:1px solid #e5e7eb; border-radius:24px; background:#fff; box-shadow:0 24px 70px rgba(0,0,0,.08); }
.auth-heading { display:flex; align-items:flex-start; gap:18px; }
.auth-heading img { width:48px; height:48px; flex:none; border-radius:14px; background:#f3f4f6; }
.auth-badge { color:#111827; font-size:11px; font-weight:900; letter-spacing:1.6px; }
h2 { margin:10px 0 8px; font-size:28px; color:#111827; }
p { margin:0; color:#6b7280; font-size:13px; line-height:1.7; }
.qr-shell { margin-top:24px; overflow:hidden; height:390px; border:1px solid #e5e7eb; border-radius:18px; background:#f7f7f8; }
.qr-frame { width:100%; height:100%; border:0; background:#fff; }
.qr-state { height:100%; display:grid; place-items:center; color:#6b7280; font-size:14px; }
.qr-actions { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:14px; }
.open-link { color:#111827; font-size:12px; font-weight:800; text-decoration:none; }
label { display:grid; gap:8px; margin-top:22px; color:#374151; font-size:12px; font-weight:800; }
label small { color:#8a8f98; font-weight:500; }
textarea, input { width:100%; border:1px solid #d1d5db; border-radius:12px; padding:12px 14px; background:#fafafa; font:inherit; color:#111827; outline:none; }
textarea { min-height:96px; resize:vertical; }
textarea:focus, input:focus { border-color:#111827; box-shadow:0 0 0 3px rgba(0,0,0,.06); }
button { width:100%; margin-top:18px; border-radius:12px; padding:13px 18px; font-weight:900; cursor:pointer; }
button:disabled { opacity:.45; cursor:not-allowed; }
.secondary { border:0; background:#111827; color:#fff; }
.ghost { border:1px solid #d1d5db; background:#fff; color:#111827; }
.ghost.small { width:auto; margin-top:0; padding:9px 12px; font-size:12px; }
.fallback { margin-top:18px; padding-top:2px; }
.auth-error { margin-top:16px; padding:11px 13px; border:1px solid rgba(239,68,68,.18); border-radius:10px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.security-note { display:block; margin-top:16px; color:#6b7280; font-size:11px; line-height:1.7; }
</style>
