<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { getStoredSession } from "../../api/auth"
import {
  getCurrentUserProfile,
  updateCurrentUserProfile,
  uploadUserAvatar,
  type CurrentUserProfile
} from "../../api/user"
import { navigation } from "../../platform/navigation"
import { showMessage, showSuccess } from "../../ui/feedback"

const loading = ref(true)
const saving = ref(false)
const avatarBusy = ref(false)
const nickname = ref("")
const avatarUrl = ref("")
const phone = ref("")
const userId = ref("")

function applyProfile(profile: CurrentUserProfile) {
  userId.value = profile.userId
  nickname.value = profile.nickname || "微信用户"
  avatarUrl.value = profile.avatarUrl || ""
  phone.value = profile.phone || ""
}

async function loadProfile() {
  if (!getStoredSession()?.accessToken) {
    showMessage("请先微信一键登录")
    navigation.back()
    return
  }
  loading.value = true
  try {
    applyProfile(await getCurrentUserProfile())
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "个人信息加载失败")
  } finally {
    loading.value = false
  }
}

function fileToBase64(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const manager = (uni as unknown as { getFileSystemManager?: () => { readFile: (options: Record<string, unknown>) => void } }).getFileSystemManager?.()
    if (!manager) {
      reject(new Error("FILE_SYSTEM_UNAVAILABLE"))
      return
    }
    manager.readFile({
      filePath,
      encoding: "base64",
      success(result: { data: string | ArrayBuffer }) {
        resolve(String(result.data))
      },
      fail() {
        reject(new Error("AVATAR_READ_FAILED"))
      }
    })
  })
}

function contentTypeOf(path: string): string {
  const lower = path.toLowerCase()
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg"
  if (lower.endsWith(".webp")) return "image/webp"
  if (lower.endsWith(".gif")) return "image/gif"
  return "image/png"
}

async function onChooseAvatar(event: { detail: { avatarUrl?: string } }) {
  const tempPath = event.detail.avatarUrl
  if (!tempPath || avatarBusy.value) return
  avatarBusy.value = true
  try {
    const dataBase64 = await fileToBase64(tempPath)
    const uploaded = await uploadUserAvatar({
      filename: tempPath.split("/").pop() || "avatar.png",
      contentType: contentTypeOf(tempPath),
      dataBase64
    })
    avatarUrl.value = uploaded.url
    showSuccess("头像已选择")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "头像上传失败")
  } finally {
    avatarBusy.value = false
  }
}

async function saveProfile() {
  const nextNickname = nickname.value.trim()
  if (!nextNickname) {
    showMessage("请填写昵称")
    return
  }
  saving.value = true
  try {
    const profile = await updateCurrentUserProfile({
      nickname: nextNickname,
      avatarUrl: avatarUrl.value || null
    })
    applyProfile(profile)
    showSuccess("个人信息已保存")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "保存失败")
  } finally {
    saving.value = false
  }
}

onShow(() => { void loadProfile() })
</script>

<template>
  <view class="safe-page custom-safe-page info-page">
    <view class="heading">
      <text class="title">个人信息</text>
      <text class="subtitle">头像和昵称会保存到账号资料，订单和陪玩主页都会读取这里。</text>
    </view>

    <view v-if="loading" class="panel loading">加载中...</view>

    <view v-else class="panel">
      <view class="avatar-row">
        <image v-if="avatarUrl" class="avatar-image" :src="avatarUrl" mode="aspectFill" />
        <view v-else class="avatar-fallback">{{ (nickname || "微").slice(0, 1).toUpperCase() }}</view>
        <button class="avatar-button" :loading="avatarBusy" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
          选择微信头像
        </button>
      </view>

      <view class="field">
        <text class="label">昵称</text>
        <input v-model="nickname" type="nickname" maxlength="80" placeholder="填写微信昵称" />
      </view>

      <view class="field readonly">
        <text class="label">手机号</text>
        <text class="readonly-value">{{ phone || "未绑定" }}</text>
      </view>

      <view class="field readonly">
        <text class="label">用户 ID</text>
        <text class="readonly-value mono">{{ userId.slice(0, 8) || "-" }}</text>
      </view>

      <button class="save-button" :loading="saving" @click="saveProfile">保存个人信息</button>
    </view>
  </view>
</template>

<style scoped>
.info-page{padding-top:24rpx}.heading{padding:8rpx 3rpx 24rpx}.title{display:block;font-size:39rpx;font-weight:850;letter-spacing:0}.subtitle{display:block;margin-top:8rpx;color:var(--muted);font-size:20rpx;line-height:1.5}.panel{padding:26rpx;border-radius:32rpx;background:#fff;box-shadow:var(--shadow-card)}.loading{text-align:center;color:var(--muted)}.avatar-row{display:flex;align-items:center;gap:22rpx;padding-bottom:24rpx;border-bottom:1rpx solid #f0eff4}.avatar-image,.avatar-fallback{width:112rpx;height:112rpx;flex:none;border-radius:32rpx}.avatar-image{display:block;background:#f2f1f7}.avatar-fallback{display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,var(--brand),#8977f3);color:#fff;font-size:38rpx;font-weight:850}.avatar-button{flex:1;height:76rpx;line-height:76rpx;margin:0;border-radius:22rpx;background:var(--brand-soft);color:var(--brand);font-size:21rpx;font-weight:780}.field{margin-top:24rpx}.label{display:block;margin-bottom:10rpx;color:#77727f;font-size:19rpx;font-weight:760}.field input{height:78rpx;padding:0 20rpx;border-radius:22rpx;background:#f7f6fb;color:var(--ink);font-size:22rpx}.readonly{display:flex;align-items:center;justify-content:space-between;gap:20rpx;padding:20rpx;border-radius:22rpx;background:#f7f6fb}.readonly .label{margin:0}.readonly-value{color:var(--ink);font-size:20rpx;font-weight:750}.mono{font-family:monospace}.save-button{height:82rpx;line-height:82rpx;margin:28rpx 0 0;border-radius:24rpx;background:var(--ink);color:#fff;font-size:23rpx;font-weight:820}
</style>
