<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import { isWeChatAuthMode } from "../../api/config"

type PlayerProfile = {
  id: string
  user_id: string
  display_name: string
  bio: string
  verification_status: "PENDING" | "APPROVED" | "REJECTED" | string
  service_status: string
}

const wechatMode = isWeChatAuthMode()
const nickname = ref(wechatMode ? "微信用户" : "Demo Customer")
const userId = ref("")
const playerName = ref("")
const playerProfile = ref<PlayerProfile | null>(null)
const playerChecked = ref(!wechatMode)
const applyOpen = ref(false)
const applyName = ref("")
const applyBio = ref("")
const applying = ref(false)

async function loadIdentity() {
  try {
    const identities = await getDemoIdentities()
    userId.value = identities.customer.userId
    nickname.value = identities.customer.nickname || (wechatMode ? "微信用户" : "Demo Customer")

    if (!wechatMode) {
      playerName.value = identities.players[0]?.displayName ?? ""
      playerChecked.value = true
      return
    }

    try {
      playerProfile.value = await request<PlayerProfile>("/player/profile", {
        userId: userId.value
      })
      playerName.value = playerProfile.value.display_name
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      if (message !== "PLAYER_PROFILE_NOT_FOUND") {
        throw error
      }
      playerProfile.value = null
      playerName.value = ""
    } finally {
      playerChecked.value = true
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "账户加载失败",
      icon: "none"
    })
  }
}

onShow(() => { void loadIdentity() })

function openPlayerWorkspace() {
  if (wechatMode && playerProfile.value?.verification_status !== "APPROVED") {
    return
  }
  uni.navigateTo({ url: "/pages-player/workbench/index" })
}

function openOrders() {
  uni.switchTab({ url: "/pages/orders/index" })
}

async function applyPlayer() {
  if (!wechatMode || !userId.value || applying.value) return
  const displayName = applyName.value.trim()
  if (!displayName) {
    uni.showToast({ title: "请填写陪玩昵称", icon: "none" })
    return
  }

  applying.value = true
  try {
    playerProfile.value = await request<PlayerProfile>("/player/apply", {
      method: "POST",
      userId: userId.value,
      data: {
        display_name: displayName,
        bio: applyBio.value.trim()
      }
    })
    playerName.value = playerProfile.value.display_name
    applyOpen.value = false
    uni.showToast({ title: "申请已提交", icon: "success" })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "申请提交失败",
      icon: "none"
    })
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <view class="page">
    <view class="profile-card">
      <view class="avatar">{{ (nickname || "微").slice(0, 1).toUpperCase() }}</view>
      <view>
        <view class="name">{{ nickname || "微信用户" }}</view>
        <view class="hint">{{ wechatMode ? "账户与订单绑定当前微信身份" : "开发环境演示身份" }}</view>
      </view>
    </view>

    <view class="menu">
      <view class="menu-item" @click="openOrders">
        <view>
          <text class="menu-title">我的订单</text>
          <text class="menu-desc">匹配、服务、完成与售后都从订单进入</text>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>

    <view
      v-if="!wechatMode || playerProfile?.verification_status === 'APPROVED'"
      class="role-card"
      @click="openPlayerWorkspace"
    >
      <view>
        <text class="role-label">陪玩工作台</text>
        <text class="role-desc">
          {{ playerName ? playerName + " · 接单、服务与收益" : "进入陪玩工作台" }}
        </text>
      </view>
      <text class="arrow light">›</text>
    </view>

    <view
      v-else-if="playerChecked && playerProfile?.verification_status === 'PENDING'"
      class="player-status-card"
    >
      <text class="status-title">陪玩申请审核中</text>
      <text class="status-desc">{{ playerProfile.display_name }} · 审核通过后这里会自动显示工作台入口。</text>
    </view>

    <view
      v-else-if="playerChecked && playerProfile?.verification_status === 'REJECTED'"
      class="player-status-card rejected"
    >
      <text class="status-title">陪玩申请未通过</text>
      <text class="status-desc">当前申请需要平台重新审核；用户下单功能不受影响。</text>
    </view>

    <view v-else-if="wechatMode && playerChecked" class="player-apply-card">
      <view v-if="!applyOpen" class="apply-entry" @click="applyOpen = true">
        <view>
          <text class="apply-title">想成为陪玩？</text>
          <text class="apply-desc">提交昵称和简介，审核通过后即可接单。</text>
        </view>
        <text class="arrow">›</text>
      </view>

      <template v-else>
        <view class="apply-head">
          <view>
            <text class="apply-title">申请成为陪玩</text>
            <text class="apply-desc">第一步只收必要资料，技能与服务通过审核后再配置。</text>
          </view>
          <text class="close" @click="applyOpen = false">取消</text>
        </view>
        <input v-model="applyName" maxlength="80" placeholder="陪玩昵称" />
        <textarea
          v-model="applyBio"
          maxlength="500"
          placeholder="简单介绍自己，可选"
        />
        <button class="apply-button" :loading="applying" @click="applyPlayer">提交申请</button>
      </template>
    </view>

    <view class="tip">
      售后、退款和联系服务者都放在对应订单详情中，不额外增加独立入口。
    </view>
  </view>
</template>

<style scoped>
.page { padding:28rpx; }
.profile-card { display:flex; gap:22rpx; align-items:center; padding:34rpx; background:#fff; border-radius:32rpx; }
.avatar { width:104rpx; height:104rpx; border-radius:32rpx; background:#6c5ce7; color:#fff; display:flex; align-items:center; justify-content:center; font-size:38rpx; font-weight:800; }
.name { font-size:32rpx; font-weight:700; }
.hint { margin-top:8rpx; color:#92929d; font-size:22rpx; }
.menu { margin-top:24rpx; overflow:hidden; border-radius:28rpx; background:#fff; }
.menu-item,.apply-entry { display:flex; align-items:center; justify-content:space-between; padding:30rpx; }
.menu-title,.apply-title { display:block; font-size:27rpx; font-weight:650; }
.menu-desc,.apply-desc { display:block; margin-top:8rpx; color:#92929d; font-size:20rpx; line-height:1.55; }
.role-card { margin-top:24rpx; padding:30rpx; border-radius:30rpx; background:#17171f; color:#fff; display:flex; align-items:center; justify-content:space-between; }
.role-label { display:block; font-size:27rpx; font-weight:700; }
.role-desc { display:block; margin-top:9rpx; color:#aaaab4; font-size:20rpx; }
.arrow { color:#b3b3bc; font-size:38rpx; }
.arrow.light { color:#777784; }
.player-status-card,.player-apply-card { margin-top:24rpx; padding:28rpx 30rpx; border-radius:28rpx; background:#fff; }
.player-status-card { background:#f1efff; color:#6157a2; }
.player-status-card.rejected { background:#fff3f3; color:#a95b5e; }
.status-title,.status-desc { display:block; }
.status-title { font-size:25rpx; font-weight:750; }
.status-desc { margin-top:8rpx; font-size:20rpx; line-height:1.55; opacity:.86; }
.player-apply-card { padding:0; overflow:hidden; }
.apply-head { display:flex; align-items:flex-start; justify-content:space-between; gap:20rpx; padding:28rpx 30rpx 12rpx; }
.close { color:#92929d; font-size:20rpx; }
.player-apply-card input,.player-apply-card textarea { width:calc(100% - 60rpx); margin:14rpx 30rpx 0; padding:20rpx; border-radius:20rpx; background:#f7f7fb; box-sizing:border-box; font-size:22rpx; }
.player-apply-card textarea { height:130rpx; }
.apply-button { margin:20rpx 30rpx 28rpx; height:78rpx; line-height:78rpx; border-radius:23rpx; background:#17171f; color:#fff; font-size:23rpx; font-weight:750; }
.tip { margin-top:22rpx; padding:24rpx 26rpx; border-radius:24rpx; background:#f0edff; color:#6f65ad; font-size:20rpx; line-height:1.6; }
</style>
