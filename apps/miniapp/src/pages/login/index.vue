<script setup lang="ts">
import { ref } from "vue"

import { bindPhoneNumber, getCurrentUserProfile, updateCurrentUserProfile, uploadUserAvatar, wxUserLogin } from "../../api/user"
import { navigation } from "../../platform/navigation"
import { showMessage, showSuccess } from "../../ui/feedback"
import type { PhoneNumberEvent } from "../../features/profile/useProfileIdentity"

const brandLogo = "/static/roots-logo.png"
const agreed = ref(false)
const loginBusy = ref(false)
const saving = ref(false)
const avatarBusy = ref(false)
const phoneBusy = ref(false)
const profileStep = ref(false)
const nickname = ref("")
const avatarUrl = ref("")
const phone = ref("")

function toggleAgree() {
  agreed.value = !agreed.value
}

async function authorizeLogin() {
  if (!agreed.value) {
    showMessage("请勾选已阅读并同意《隐私协议》及《服务协议》")
    return
  }
  if (loginBusy.value) return
  loginBusy.value = true
  try {
    await wxUserLogin()
    const profile = await getCurrentUserProfile()
    nickname.value = profile.nickname || ""
    avatarUrl.value = profile.avatarUrl || ""
    phone.value = profile.phone || ""
    profileStep.value = true
    showSuccess("登录成功")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "微信登录失败")
  } finally {
    loginBusy.value = false
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
    showSuccess("头像已获取")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "头像上传失败")
  } finally {
    avatarBusy.value = false
  }
}

async function onGetPhoneNumber(event: PhoneNumberEvent) {
  if (phoneBusy.value) return
  phoneBusy.value = true
  try {
    const result = await bindPhoneNumber(event.detail)
    phone.value = result.phone
    showSuccess("手机号已授权")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "手机号授权失败")
  } finally {
    phoneBusy.value = false
  }
}

async function completeProfile() {
  const nextNickname = nickname.value.trim()
  if (!nextNickname) {
    showMessage("请填写昵称")
    return
  }
  saving.value = true
  try {
    await updateCurrentUserProfile({
      nickname: nextNickname,
      avatarUrl: avatarUrl.value || null
    })
    showSuccess("资料已保存")
    navigation.tab("/pages/profile/index")
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "资料保存失败")
  } finally {
    saving.value = false
  }
}

function openAgreement(type: "privacy" | "service") {
  showMessage(type === "privacy" ? "隐私协议暂未配置" : "服务协议暂未配置")
}
</script>

<template>
  <view class="login-page">
    <view class="back" @click="navigation.back()">‹</view>
    <view class="hero-blur"></view>

    <view class="brand-stage">
      <image class="brand-logo" :src="brandLogo" mode="aspectFit" />
      <text class="brand-name">若水电竞</text>
      <text class="brand-subtitle">微信登录后同步订单、手机号和个人资料</text>
    </view>

    <view v-if="!profileStep" class="login-card">
      <button class="login-button" :loading="loginBusy" @click="authorizeLogin">授权登录</button>
      <view class="agreement-row" @click="toggleAgree">
        <view :class="['checkbox', { checked: agreed }]"><text v-if="agreed">✓</text></view>
        <text class="agreement-text">已阅读并同意</text>
        <text class="agreement-link" @click.stop="openAgreement('privacy')">《隐私协议》</text>
        <text class="agreement-text">及</text>
        <text class="agreement-link" @click.stop="openAgreement('service')">《服务协议》</text>
      </view>
    </view>

    <view v-else class="auth-mask">
      <view class="auth-sheet">
        <view class="sheet-title-row">
          <image class="sheet-logo" :src="brandLogo" mode="aspectFit" />
          <text class="sheet-title">若水电竞申请使用</text>
        </view>
        <text class="sheet-desc">完善头像和昵称，享受更多优质服务</text>

        <view class="auth-field avatar-field">
          <text class="field-label">头像</text>
          <button class="avatar-picker" :loading="avatarBusy" open-type="chooseAvatar" @chooseavatar="onChooseAvatar">
            <image v-if="avatarUrl" class="picked-avatar" :src="avatarUrl" mode="aspectFill" />
            <text v-else>获取头像</text>
          </button>
        </view>

        <view class="auth-field">
          <text class="field-label">昵称</text>
          <input v-model="nickname" type="nickname" maxlength="80" placeholder="请输入昵称" />
        </view>

        <view class="auth-field">
          <text class="field-label">手机号</text>
          <button class="phone-button" :loading="phoneBusy" open-type="getPhoneNumber" @getphonenumber="onGetPhoneNumber">
            {{ phone || "授权手机号" }}
          </button>
        </view>

        <button class="allow-button" :loading="saving" @click="completeProfile">允许</button>
        <button class="deny-button" @click="navigation.tab('/pages/profile/index')">拒绝</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.login-page{position:relative;min-height:100vh;overflow:hidden;background:linear-gradient(180deg,#eaf8ff 0%,#ffffff 42%,#f8fafc 100%);color:#111827}.back{position:fixed;left:36rpx;top:82rpx;z-index:5;width:56rpx;height:56rpx;line-height:50rpx;text-align:center;color:#111827;font-size:52rpx}.hero-blur{position:absolute;left:0;right:0;top:0;height:430rpx;background:radial-gradient(circle at 50% 0,rgba(56,189,248,.22),transparent 62%)}.brand-stage{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;padding-top:500rpx}.brand-logo{width:158rpx;height:158rpx;border-radius:32rpx;box-shadow:0 24rpx 70rpx rgba(15,23,42,.22)}.brand-name{margin-top:38rpx;color:#ffffff;text-shadow:0 4rpx 14rpx rgba(0,0,0,.36);font-size:39rpx;font-weight:900;letter-spacing:2rpx}.brand-subtitle{margin-top:14rpx;color:#94a3b8;font-size:21rpx}.login-card{position:relative;z-index:1;margin:132rpx 70rpx 0}.login-button{height:88rpx;line-height:88rpx;margin:0;border-radius:18rpx;background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;font-size:25rpx;font-weight:850;box-shadow:0 16rpx 32rpx rgba(14,165,233,.26)}.agreement-row{display:flex;align-items:center;justify-content:center;gap:8rpx;margin-top:72rpx;min-height:48rpx}.checkbox{width:38rpx;height:38rpx;display:flex;align-items:center;justify-content:center;border:2rpx solid #d1d5db;border-radius:6rpx;background:#fff;color:#0284c7;font-size:25rpx;font-weight:900}.checkbox.checked{border-color:#0284c7;background:#eff6ff}.agreement-text{color:#9ca3af;font-size:20rpx}.agreement-link{color:#0284c7;font-size:20rpx}.auth-mask{position:fixed;inset:0;z-index:10;display:flex;align-items:flex-end;background:rgba(0,0,0,.55)}.auth-sheet{width:100%;padding:36rpx 48rpx 44rpx;border-radius:22rpx 22rpx 0 0;background:#fff}.sheet-title-row{display:flex;align-items:center;gap:18rpx}.sheet-logo{width:52rpx;height:52rpx;border-radius:10rpx}.sheet-title{color:#111827;font-size:28rpx;font-weight:900}.sheet-desc{display:block;margin:24rpx 0 42rpx;color:#ef4444;font-size:24rpx;font-weight:760}.auth-field{display:flex;align-items:center;gap:28rpx;margin-top:28rpx}.field-label{width:90rpx;color:#374151;font-size:27rpx}.avatar-picker{width:112rpx;height:112rpx;line-height:112rpx;margin:0;padding:0;border:1rpx dashed #d1d5db;border-radius:56rpx;background:#fff;color:#a1a1aa;font-size:20rpx}.picked-avatar{width:100%;height:100%;border-radius:56rpx}.auth-field input{flex:1;height:84rpx;padding:0 22rpx;border:1rpx solid #e5e7eb;border-radius:4rpx;background:#fff;color:#111827;font-size:24rpx}.phone-button{flex:1;height:84rpx;line-height:84rpx;margin:0;border-radius:8rpx;background:#f3f4f6;color:#111827;font-size:23rpx}.allow-button{height:88rpx;line-height:88rpx;margin:46rpx 0 0;border-radius:44rpx;background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;font-size:26rpx;font-weight:850}.deny-button{height:74rpx;line-height:74rpx;margin:18rpx 0 0;background:transparent;color:#9ca3af;font-size:24rpx}
</style>
