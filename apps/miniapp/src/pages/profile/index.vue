<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Wallet } from "../../types/domain"

const nickname = ref("Demo Customer")
const playerName = ref("")
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })

function openPlayerWorkspace() {
  uni.navigateTo({ url: "/pages-player/workbench/index" })
}

function openOrders() {
  uni.switchTab({ url: "/pages/orders/index" })
}

onShow(async () => {
  try {
    const identities = await getDemoIdentities()
    nickname.value = identities.customer.nickname
    playerName.value = identities.players[0]?.displayName ?? ""

    try {
      wallet.value = await request<Wallet>("/wallet", {
        userId: identities.customer.userId
      })
    } catch {
      // Wallet is optional in the customer demo surface.
    }
  } catch {
    // Keep profile usable when the demo backend is unavailable.
  }
})
</script>

<template>
  <view class="page">
    <view class="profile-card">
      <view class="avatar">{{ nickname.slice(0, 1).toUpperCase() }}</view>
      <view class="profile-copy"><view class="name">{{ nickname }}</view><view class="hint">开发环境模拟微信身份</view></view>
      <view class="role">用户端</view>
    </view>

    <view class="wallet-card">
      <view class="wallet-head"><text>我的钱包</text><text class="wallet-link">明细 ›</text></view>
      <view class="balance">¥{{ ((wallet?.availableBalance || 0)/100).toFixed(2) }}</view>
      <view class="wallet-meta"><text>可用余额</text><text>冻结 ¥{{ ((wallet?.frozenBalance || 0)/100).toFixed(2) }}</text></view>
    </view>

    <view class="menu">
      <view class="menu-item" @click="openOrders"><view><text class="menu-icon">单</text><text>我的订单</text></view><text class="arrow">›</text></view>
      <view class="menu-item" @click="openPlayerWorkspace"><view><text class="menu-icon purple">陪</text><text>切换陪玩工作台</text></view><text class="arrow">›</text></view>
      <view class="menu-item"><view><text class="menu-icon green">盾</text><text>{{ playerName ? "陪玩身份已配置" : "陪玩身份待配置" }}</text></view><text class="arrow">›</text></view>
    </view>

    </view>
</template>

<style scoped>
.page { padding:28rpx; }
.profile-card { display:flex; gap:20rpx; align-items:center; padding:30rpx; background:#fff; border-radius:32rpx; box-shadow:0 12rpx 36rpx rgba(25,20,60,.05); }
.avatar { width:98rpx; height:98rpx; flex:none; border-radius:31rpx; background:linear-gradient(145deg,#17171f,#363342); color:#fff; display:flex; align-items:center; justify-content:center; font-size:36rpx; font-weight:850; }
.profile-copy { flex:1; min-width:0; }
.name { font-size:30rpx; font-weight:800; }
.hint { margin-top:7rpx; color:#9999a4; font-size:20rpx; }
.role { padding:8rpx 13rpx; border-radius:999rpx; background:#f1efff; color:#6c5ce7; font-size:18rpx; font-weight:700; }
.wallet-card { margin-top:20rpx; padding:30rpx; border-radius:32rpx; background:linear-gradient(145deg,#6854df,#8b78f1); color:#fff; }
.wallet-head { display:flex; justify-content:space-between; font-size:21rpx; }
.wallet-link { opacity:.72; }
.balance { margin-top:20rpx; font-size:48rpx; font-weight:850; }
.wallet-meta { display:flex; gap:22rpx; margin-top:8rpx; color:rgba(255,255,255,.72); font-size:18rpx; }
.menu { margin-top:20rpx; overflow:hidden; border-radius:30rpx; background:#fff; }
.menu-item { display:flex; justify-content:space-between; align-items:center; padding:26rpx 28rpx; border-bottom:1rpx solid #f1f1f5; font-size:25rpx; }
.menu-item:last-child { border:0; }
.menu-item>view { display:flex; align-items:center; gap:18rpx; }
.menu-icon { width:48rpx; height:48rpx; display:flex; align-items:center; justify-content:center; border-radius:15rpx; background:#f3f3f6; color:#555560; font-size:18rpx; font-weight:800; }
.menu-icon.purple { background:#f0edff; color:#6c5ce7; }
.menu-icon.green { background:#eafbf2; color:#1f9d5d; }
.arrow { color:#b5b5bd; font-size:30rpx; }
.dev-card { margin-top:20rpx; padding:28rpx; border:1rpx dashed #d8d8e1; border-radius:30rpx; background:rgba(255,255,255,.72); }
.dev-head { display:flex; align-items:center; gap:10rpx; }
.label { font-size:23rpx; font-weight:750; }
.dev-tag { padding:4rpx 8rpx; border-radius:8rpx; background:#17171f; color:#fff; font-size:14rpx; letter-spacing:1rpx; }
.dev-card input { height:76rpx; margin:18rpx 0; padding:0 18rpx; border-radius:18rpx; background:#f7f7fb; font-size:21rpx; }
.secondary { height:72rpx; line-height:72rpx; border-radius:20rpx; background:#f0edff; color:#6c5ce7; font-size:22rpx; font-weight:700; }
</style>
