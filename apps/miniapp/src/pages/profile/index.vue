<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"
import { ref } from "vue"

import { getDemoIdentities } from "../../api/demo"

const nickname = ref("Demo Customer")
const playerName = ref("Demo Player")

onShow(async () => {
  try {
    const identities = await getDemoIdentities()
    nickname.value = identities.customer.nickname
    playerName.value = identities.players[0]?.displayName ?? "尚无陪玩身份"
  } catch {
    // Keep local demo labels when backend is unavailable.
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
      <view class="avatar">U</view>
      <view>
        <view class="name">{{ nickname }}</view>
        <view class="hint">Mock WeChat Login · {{ playerName }}</view>
      </view>
    </view>

    <view class="menu">
      <view class="menu-item" @click="openPlayerWorkspace">
        <text>陪玩工作台</text>
        <text class="arrow">›</text>
      </view>
      <view class="menu-item" @click="openOrders">
        <text>我的订单</text>
        <text class="arrow">›</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.profile-card { display: flex; gap: 22rpx; align-items: center; padding: 34rpx; background: white; border-radius: 32rpx; }
.avatar { width: 104rpx; height: 104rpx; border-radius: 32rpx; background: #6c5ce7; color: white; display: flex; align-items: center; justify-content: center; font-size: 38rpx; font-weight: 800; }
.name { font-size: 32rpx; font-weight: 700; }
.hint { margin-top: 8rpx; color: #92929d; font-size: 22rpx; }
.menu { margin-top: 30rpx; overflow: hidden; border-radius: 28rpx; background: white; }
.menu-item { display: flex; justify-content: space-between; padding: 30rpx; border-bottom: 1rpx solid #f0f0f4; font-size: 28rpx; }
.arrow { color: #b3b3bc; }
</style>
