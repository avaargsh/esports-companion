<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order, Wallet } from "../../types/domain"
import OfferingPanel from "./OfferingPanel.vue"
import SkillPanel from "./SkillPanel.vue"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

const profile = ref<Player | null>(null)
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
const orders = ref<Order[]>([])
const playerUserId = ref("")
const busy = ref(false)
const serviceSettingsOpen = ref(false)

const online = computed(() => profile.value?.service_status === "AVAILABLE")
const verified = computed(() => profile.value?.verification_status === "APPROVED")
const acceptedCount = computed(() => orders.value.filter(item => item.status === "ACCEPTED").length)
const inServiceCount = computed(() => orders.value.filter(item => item.status === "IN_SERVICE").length)
const waitingConfirmCount = computed(() => orders.value.filter(item => item.status === "FINISH_REQUESTED").length)
const activeIncome = computed(() =>
  orders.value
    .filter(item => ["ACCEPTED", "IN_SERVICE", "FINISH_REQUESTED"].includes(item.status))
    .reduce((sum, item) => sum + item.player_amount, 0)
)

async function load() {
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  if (!playerUserId.value) return

  const [profileResult, walletResult, orderResult] = await Promise.all([
    request<Player>("/player/profile", { userId: playerUserId.value }),
    request<Wallet>("/wallet", { userId: playerUserId.value }),
    request<Order[]>("/player/orders", { userId: playerUserId.value })
  ])
  profile.value = profileResult
  wallet.value = walletResult
  orders.value = orderResult
}

async function toggleStatus() {
  if (!profile.value || !playerUserId.value || busy.value) return
  if (!verified.value) {
    uni.showToast({ title: "认证通过后才能开启接单", icon: "none" })
    return
  }
  busy.value = true
  try {
    profile.value = await request<Player>("/player/profile", {
      method: "PUT",
      userId: playerUserId.value,
      data: { service_status: online.value ? "OFFLINE" : "AVAILABLE" }
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

function openOrders() {
  uni.navigateTo({ url: "/pages-player/orders/index" })
}

function openWithdrawals() {
  uni.navigateTo({ url: "/pages-player/withdrawals/index" })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="summary">
      <view class="topline">
        <view>
          <text class="label">可用收益</text>
          <view class="amount">¥ {{ (wallet.availableBalance / 100).toFixed(2) }}</view>
          <text class="earnings-link" @click="openWithdrawals">收益与提现 ›</text>
        </view>
        <view class="status" :class="{ off: !online, disabled: !verified }" @click="toggleStatus">
          ● {{ !verified ? "待认证" : online ? "接单中" : "已下线" }}
        </view>
      </view>

      <view class="identity">
        <view>
          <view class="player-name">{{ profile?.display_name || "Demo Player" }}</view>
          <view class="verify">
            {{ profile?.verification_status === "APPROVED" ? "已认证陪玩" : "认证状态：" + (profile?.verification_status || "-") }}
          </view>
        </view>
        <view class="frozen">
          <text>冻结中</text>
          <b>¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</b>
        </view>
      </view>

      <view class="fulfillment-stats">
        <view><b>{{ acceptedCount }}</b><text>待开始</text></view>
        <view><b>{{ inServiceCount }}</b><text>服务中</text></view>
        <view><b>{{ waitingConfirmCount }}</b><text>待确认</text></view>
      </view>

      <view class="active-income">
        <text>履约中预计收入</text>
        <b>¥{{ (activeIncome / 100).toFixed(2) }}</b>
      </view>

      <view class="actions">
        <button class="primary" @click="openPool">去抢单</button>
        <button class="secondary" @click="openOrders">服务订单</button>
      </view>
    </view>

    <view class="settings-entry" @click="serviceSettingsOpen = !serviceSettingsOpen">
      <view>
        <text class="settings-title">我的服务</text>
        <text class="settings-desc">服务套餐与技能认证</text>
      </view>
      <text class="settings-arrow">{{ serviceSettingsOpen ? "⌃" : "›" }}</text>
    </view>

    <template v-if="serviceSettingsOpen">
      <OfferingPanel v-if="playerUserId" :user-id="playerUserId" />
      <SkillPanel v-if="playerUserId" :user-id="playerUserId" />
    </template>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#0f0f15; box-sizing:border-box; }
.summary { padding:36rpx; border-radius:36rpx; background:linear-gradient(145deg,#1a1922,#242131); color:#fff; }
.topline { display:flex; justify-content:space-between; align-items:flex-start; }
.label { color:#aaaab4; font-size:22rpx; }
.amount { margin-top:12rpx; font-size:54rpx; font-weight:800; }
.earnings-link { display:block; margin-top:9rpx; color:#9b8cff; font-size:19rpx; }
.status { padding:12rpx 18rpx; border-radius:999rpx; background:rgba(34,197,94,.14); color:#5ddb8b; font-size:22rpx; }
.status.off { background:rgba(255,255,255,.08); color:#aaaab4; }
.status.disabled { background:rgba(245,158,11,.12); color:#e6b455; }
.identity { margin-top:42rpx; padding-top:30rpx; border-top:1rpx solid rgba(255,255,255,.08); display:flex; align-items:flex-end; justify-content:space-between; gap:20rpx; }
.player-name { font-size:30rpx; font-weight:700; }
.verify { margin-top:8rpx; color:#aaaab4; font-size:21rpx; }
.frozen { text-align:right; color:#777784; font-size:19rpx; }
.frozen text,.frozen b { display:block; }
.frozen b { margin-top:5rpx; color:#c8c4dc; font-size:24rpx; }
.fulfillment-stats { display:flex; gap:12rpx; margin-top:30rpx; }
.fulfillment-stats view { flex:1; padding:18rpx 10rpx; border-radius:20rpx; background:rgba(255,255,255,.06); text-align:center; }
.fulfillment-stats b { display:block; font-size:28rpx; }
.fulfillment-stats text { display:block; margin-top:5rpx; color:#8e8e99; font-size:17rpx; }
.active-income { display:flex; justify-content:space-between; align-items:center; margin-top:16rpx; padding:18rpx 20rpx; border-radius:20rpx; background:rgba(108,92,231,.12); color:#b7aff2; font-size:19rpx; }
.active-income b { color:#fff; font-size:24rpx; }
.actions { display:flex; gap:16rpx; margin-top:24rpx; }
.actions button { flex:1; margin:0; }
.primary,.secondary { height:84rpx; line-height:84rpx; border-radius:26rpx; font-size:25rpx; font-weight:700; }
.primary { background:#6c5ce7; color:#fff; }
.secondary { background:rgba(255,255,255,.08); color:#fff; }
.settings-entry { display:flex; align-items:center; justify-content:space-between; margin-top:22rpx; padding:26rpx 28rpx; border-radius:26rpx; background:#181820; color:#fff; }
.settings-title,.settings-desc { display:block; }
.settings-title { font-size:25rpx; font-weight:700; }
.settings-desc { margin-top:6rpx; color:#777783; font-size:19rpx; }
.settings-arrow { color:#777783; font-size:34rpx; }
</style>
