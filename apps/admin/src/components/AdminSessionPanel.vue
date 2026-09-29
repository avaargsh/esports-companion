<script setup lang="ts">
import { ref } from "vue"

import { adminRequest, setAdminSession } from "../api"

const emit = defineEmits<{ ready: [] }>()
const accessToken = ref("")
const refreshToken = ref("")
const error = ref("")
const busy = ref(false)

async function submit() {
  if (busy.value) return
  error.value = ""
  busy.value = true
  try {
    setAdminSession(accessToken.value, refreshToken.value)
    const me = await adminRequest<{ roles: string[] }>("/auth/me")
    if (!me.roles.includes("PLATFORM")) {
      throw new Error("PLATFORM_REQUIRED")
    }
    emit("ready")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "认证失败"
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="auth-card">
    <div class="auth-badge">SECURE OPERATOR SESSION</div>
    <h2>连接运营账号</h2>
    <p>
      安全环境不接受 X-Admin-Id。粘贴由平台认证流程签发的 PLATFORM Bearer Token；
      如同时提供 Refresh Token，过期后会自动轮换一次。
    </p>
    <label>
      Access Token
      <textarea
        v-model="accessToken"
        autocomplete="off"
        spellcheck="false"
        placeholder="Bearer access token（不要包含 Bearer 前缀）"
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
    <div v-if="error" class="auth-error">{{ error }}</div>
    <button :disabled="!accessToken.trim() || busy" @click="submit">
      {{ busy ? "正在校验…" : "校验并进入运营台" }}
    </button>
    <small class="security-note">
      Token 仅保存在当前浏览器 sessionStorage，不会写入构建产物或源码。
    </small>
  </section>
</template>

<style scoped>
.auth-card { max-width:720px; margin:70px auto; padding:34px; border:1px solid #e9e8ef; border-radius:24px; background:#fff; box-shadow:0 24px 70px rgba(30,23,70,.06); }
.auth-badge { color:#6c5ce7; font-size:11px; font-weight:900; letter-spacing:1.6px; }
h2 { margin:12px 0 8px; font-size:26px; }
p { color:#7d7d89; font-size:13px; line-height:1.7; }
label { display:grid; gap:8px; margin-top:20px; color:#555560; font-size:12px; font-weight:700; }
label small { color:#9999a4; font-weight:500; }
textarea, input { width:100%; border:1px solid #dedde6; border-radius:12px; padding:12px 14px; background:#fafafd; font:inherit; color:#292933; outline:none; }
textarea { min-height:100px; resize:vertical; }
textarea:focus, input:focus { border-color:#8b7cf6; box-shadow:0 0 0 3px rgba(108,92,231,.08); }
button { margin-top:22px; border:0; border-radius:12px; padding:12px 18px; background:#6c5ce7; color:#fff; font-weight:800; cursor:pointer; }
button:disabled { opacity:.45; cursor:not-allowed; }
.auth-error { margin-top:16px; padding:10px 12px; border-radius:10px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.security-note { display:block; margin-top:14px; color:#aaaab4; font-size:11px; }
</style>
