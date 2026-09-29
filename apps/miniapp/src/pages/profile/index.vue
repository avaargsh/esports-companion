<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { getDemoIdentities } from "../../api/demo"

const nickname = ref("Demo Customer")
const playerName = ref("")

onShow(async () => {
  try {
    const identities = await getDemoIdentities()
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
        <view class="hint">账户与订单都绑定当前微信身份</view>
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

    <view class="role-card" @click="openPlayerWorkspace">
      <view>
        <text class="role-label">我是陪玩</text>
        <text class="role-desc">
          {{ playerName ? playerName + " · 接单、服务与收益" : "进入陪玩工作台" }}
        </text>
      </view>
      <text class="arrow light">›</text>
    </view>

    <view class="tip">
      售后、退款和联系服务者都放在对应订单详情中，不额外增加独立入口。
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.profile-card { display:flex; gap:22rpx; align-items:center; padding:34rpx; background:#fff; border-radius:32rpx; }
.avatar { width:104rpx; height:104rpx; border-radius:32rpx; background:#6c5ce7; color:#fff; display:flex; align-items:center; justify-content:center; font-size:38rpx; font-weight:800; }
.name { font-size:32rpx; font-weight:700; }
.hint { margin-top:8rpx; color:#92929d; font-size:22rpx; }
.menu { margin-top:24rpx; overflow:hidden; border-radius:28rpx; background:#fff; }
.menu-item { display:flex; align-items:center; justify-content:space-between; padding:30rpx; }
.menu-title { display:block; font-size:27rpx; font-weight:650; }
.menu-desc { display:block; margin-top:8rpx; color:#92929d; font-size:20rpx; }
.role-card { margin-top:24rpx; padding:30rpx; border-radius:30rpx; background:#17171f; color:#fff; display:flex; align-items:center; justify-content:space-between; }
.role-label { display:block; font-size:27rpx; font-weight:700; }
.role-desc { display:block; margin-top:9rpx; color:#aaaab4; font-size:20rpx; }
.arrow { color:#b3b3bc; font-size:38rpx; }
.arrow.light { color:#777784; }
.tip { margin-top:22rpx; padding:24rpx 26rpx; border-radius:24rpx; background:#f0edff; color:#6f65ad; font-size:20rpx; line-height:1.6; }
</style>
