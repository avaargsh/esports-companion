<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { getRuntimeIdentities } from "../../api/identity"
import { usesWechatSession } from "../../api/session"

const nickname = ref("Demo Customer")
const playerName = ref("")
const productionIdentity = usesWechatSession()

onShow(async () => {
  try {
    const identities = await getRuntimeIdentities()
    nickname.value = identities.customer.nickname
    playerName.value = identities.players[0]?.displayName ?? ""
  } catch {
    // Keep the page usable if the backend is temporarily unavailable.
  }
})

function openPlayerWorkspace() {
  uni.navigateTo({ url: "/pages-player/workbench/index" })
}

function openOrders() {
  uni.switchTab({ url: "/pages/orders/index" })
}
</script>

<template>
  <view class="page">
    <view class="profile-card">
      <view class="avatar">{{ nickname.slice(0, 1).toUpperCase() }}</view>
      <view>
        <view class="name">{{ nickname }}</view>
        <view class="hint">
          {{ productionIdentity ? "微信登录身份" : "开发环境模拟微信身份" }}
        </view>
      </view>
    </view>

    <view class="role-card" @click="openPlayerWorkspace">
      <view>
        <text class="role-label">陪玩工作台</text>
        <text class="role-desc">
          {{ playerName
            ? playerName + " · 查看接单与收益"
            : productionIdentity
              ? "当前账号尚未通过陪玩认证"
              : "未找到 Demo Player，请先运行 seed" }}
        </text>
      </view>
      <text class="arrow light">›</text>
    </view>

    <view class="menu">
      <view class="menu-item" @click="openOrders">
        <view>
          <text class="menu-title">我的订单</text>
          <text class="menu-desc">查看匹配、服务与结算状态</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <view class="menu-item">
        <view>
          <text class="menu-title">客服与争议</text>
          <text class="menu-desc">后续接退款 / DISPUTED 流程</text>
        </view>
        <text class="soon">待接入</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.profile-card { display: flex; gap: 22rpx; align-items: center; padding: 34rpx; background: #fff; border-radius: 32rpx; }
.avatar { width: 104rpx; height: 104rpx; border-radius: 32rpx; background: #6c5ce7; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 38rpx; font-weight: 800; }
.name { font-size: 32rpx; font-weight: 700; }
.hint { margin-top: 8rpx; color: #92929d; font-size: 22rpx; }
.role-card { margin-top: 24rpx; padding: 30rpx; border-radius: 30rpx; background: #17171f; color: #fff; display: flex; align-items: center; justify-content: space-between; }
.role-label { display: block; font-size: 29rpx; font-weight: 700; }
.role-desc { display: block; margin-top: 10rpx; color: #aaaab4; font-size: 21rpx; }
.menu { margin-top: 24rpx; overflow: hidden; border-radius: 28rpx; background: #fff; }
.menu-item { display: flex; align-items: center; justify-content: space-between; padding: 30rpx; border-bottom: 1rpx solid #f0f0f4; }
.menu-item:last-child { border-bottom: 0; }
.menu-title { display: block; font-size: 27rpx; font-weight: 600; }
.menu-desc { display: block; margin-top: 8rpx; color: #92929d; font-size: 20rpx; }
.arrow { color: #b3b3bc; font-size: 38rpx; }
.arrow.light { color: #777784; }
.soon { color: #aaaab4; font-size: 20rpx; }
</style>
