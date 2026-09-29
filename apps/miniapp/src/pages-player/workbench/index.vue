<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Wallet } from "../../types/domain"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

const profile = ref<Player | null>(null)
const wallet = ref<Wallet | null>(null)
const playerUserId = ref("")
const accepting = ref(false)
const busy = ref(false)

const available = computed(() =>
  ((wallet.value?.availableBalance || 0) / 100).toFixed(2)
)
const frozen = computed(() =>
  ((wallet.value?.frozenBalance || 0) / 100).toFixed(2)
)

async function load() {
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  if (!playerUserId.value) return

  const [profileResult, walletResult] = await Promise.all([
    request<Player>("/player/profile", { userId: playerUserId.value }),
    request<Wallet>("/wallet", { userId: playerUserId.value })
  ])
  profile.value = profileResult
  wallet.value = walletResult
  accepting.value = profileResult.service_status === "AVAILABLE"
}

async function toggleAccepting() {
  if (!profile.value || !playerUserId.value || busy.value) return
  busy.value = true
  try {
    const next = accepting.value ? "OFFLINE" : "AVAILABLE"
    profile.value = await request<Player>("/player/profile", {
      method: "PATCH",
      userId: playerUserId.value,
      data: { service_status: next }
    })
    accepting.value = profile.value.service_status === "AVAILABLE"
    uni.showToast({
      title: accepting.value ? "已开启接单" : "已暂停接单",
      icon: "none"
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "状态切换失败",
      icon: "none"
    })
  } finally {
    busy.value = false
  }
}

function openPool() {
  uni.navigateTo({ url: "/pages-player/order-pool/index" })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="topbar">
      <view>
        <text class="eyebrow">PLAYER CONSOLE</text>
        <view class="title">陪玩工作台</view>
      </view>
      <view class="availability" :class="{off:!accepting}" @click="toggleAccepting">
        <text class="dot"></text>{{ accepting ? "接单中" : "已暂停" }}
      </view>
    </view>

    <view class="balance-card">
      <view class="card-top">
        <view><text class="label">可提现收益</text><view class="amount">¥ {{ available }}</view></view>
        <view class="wallet-mark">¥</view>
      </view>
      <view class="balance-meta">
        <view><text class="meta-value">¥{{ frozen }}</text><text class="meta-name">冻结收益</text></view>
        <view><text class="meta-value">--</text><text class="meta-name">本月收益</text></view>
        <view><text class="meta-value">--</text><text class="meta-name">待结算</text></view>
      </view>
    </view>

    <view class="section-head">
      <view><text class="section-title">今日概览</text><text class="section-sub">服务数据会随订单实时更新</text></view>
    </view>

    <view class="stats">
      <view class="stat"><view class="stat-icon purple">单</view><text class="num">0</text><text class="name">今日订单</text></view>
      <view class="stat"><view class="stat-icon green">✓</view><text class="num">--</text><text class="name">完成率</text></view>
      <view class="stat"><view class="stat-icon orange">★</view><text class="num">--</text><text class="name">好评率</text></view>
    </view>

    <view class="action-card" @click="openPool">
      <view class="action-icon">⚡</view>
      <view class="action-copy">
        <text class="action-title">进入抢单大厅</text>
        <text class="action-desc">{{ accepting ? "查看与你技能匹配的新订单" : "当前已暂停接单，可浏览但建议先恢复状态" }}</text>
      </view>
      <text class="arrow">›</text>
    </view>

    <view class="notice">
      <view class="notice-title">履约提醒</view>
      <view class="notice-item"><text>01</text><view><text class="notice-main">接单后及时响应</text><text class="notice-sub">减少用户等待时间，避免超时取消。</text></view></view>
      <view class="notice-item"><text>02</text><view><text class="notice-main">服务完成后发起确认</text><text class="notice-sub">用户确认后，收入才会进入结算流程。</text></view></view>
    </view>

    <button class="primary" @click="openPool">去抢单</button>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)); background:#0f0f15; color:#fff; }
.topbar { display:flex; justify-content:space-between; align-items:flex-end; padding:14rpx 2rpx 28rpx; }
.eyebrow { color:#686874; font-size:17rpx; letter-spacing:3rpx; }
.title { margin-top:7rpx; font-size:37rpx; font-weight:850; }
.availability { display:flex; align-items:center; gap:8rpx; padding:10rpx 15rpx; border-radius:999rpx; background:rgba(34,197,94,.12); color:#5dda8b; font-size:19rpx; }
.availability.off { background:rgba(148,148,160,.12); color:#92929d; }
.dot { width:12rpx; height:12rpx; border-radius:50%; background:currentColor; }
.balance-card { padding:34rpx; border-radius:36rpx; background:linear-gradient(145deg,#6651dc,#806df0 62%,#9785f7); box-shadow:0 22rpx 54rpx rgba(92,73,215,.20); }
.card-top { display:flex; justify-content:space-between; align-items:flex-start; }
.label { color:rgba(255,255,255,.72); font-size:20rpx; }
.amount { margin-top:10rpx; font-size:52rpx; font-weight:850; letter-spacing:-2rpx; }
.wallet-mark { width:72rpx; height:72rpx; display:flex; align-items:center; justify-content:center; border-radius:24rpx; background:rgba(255,255,255,.13); font-size:28rpx; font-weight:850; }
.balance-meta { display:flex; margin-top:34rpx; padding-top:26rpx; border-top:1rpx solid rgba(255,255,255,.14); }
.balance-meta view { flex:1; }
.meta-value { display:block; font-size:24rpx; font-weight:750; }
.meta-name { display:block; margin-top:5rpx; color:rgba(255,255,255,.58); font-size:17rpx; }
.section-head { margin-top:34rpx; margin-bottom:16rpx; }
.section-title { display:block; font-size:27rpx; font-weight:800; }
.section-sub { display:block; margin-top:5rpx; color:#6f6f7b; font-size:18rpx; }
.stats { display:flex; gap:12rpx; }
.stat { flex:1; padding:24rpx 10rpx; border:1rpx solid rgba(255,255,255,.045); border-radius:26rpx; background:#18181f; text-align:center; }
.stat-icon { width:44rpx; height:44rpx; margin:0 auto 14rpx; display:flex; align-items:center; justify-content:center; border-radius:14rpx; font-size:17rpx; font-weight:850; }
.stat-icon.purple { background:rgba(108,92,231,.15); color:#9587f6; }
.stat-icon.green { background:rgba(34,197,94,.13); color:#56d587; }
.stat-icon.orange { background:rgba(245,158,11,.13); color:#eeb24f; }
.num { display:block; font-size:28rpx; font-weight:800; }
.name { display:block; margin-top:5rpx; color:#777783; font-size:17rpx; }
.action-card { display:flex; align-items:center; gap:18rpx; margin-top:18rpx; padding:26rpx; border:1rpx solid rgba(255,255,255,.05); border-radius:30rpx; background:#191920; }
.action-icon { width:62rpx; height:62rpx; flex:none; display:flex; align-items:center; justify-content:center; border-radius:20rpx; background:#29243e; font-size:25rpx; }
.action-copy { flex:1; min-width:0; }
.action-title { display:block; font-size:24rpx; font-weight:750; }
.action-desc { display:block; margin-top:5rpx; color:#777783; font-size:18rpx; line-height:1.45; }
.arrow { color:#666672; font-size:34rpx; }
.notice { margin-top:18rpx; padding:28rpx; border:1rpx solid rgba(255,255,255,.045); border-radius:30rpx; background:#16161d; }
.notice-title { margin-bottom:18rpx; font-size:23rpx; font-weight:750; }
.notice-item { display:flex; gap:15rpx; margin-top:14rpx; }
.notice-item>text { width:38rpx; height:38rpx; flex:none; display:flex; align-items:center; justify-content:center; border-radius:12rpx; background:#22222b; color:#747480; font-size:14rpx; }
.notice-main { display:block; color:#bdbdc5; font-size:19rpx; font-weight:650; }
.notice-sub { display:block; margin-top:4rpx; color:#666672; font-size:17rpx; line-height:1.5; }
.primary { margin-top:22rpx; height:84rpx; line-height:84rpx; border-radius:25rpx; background:#6c5ce7; color:#fff; font-size:25rpx; font-weight:750; }
</style>
