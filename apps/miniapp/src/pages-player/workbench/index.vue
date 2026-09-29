<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"
import { computed, ref } from "vue"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

type Order = {
  id: string
  order_no: string
  status: string
  total_amount: number
  player_amount: number
  version: number
}

type Wallet = {
  id?: string
  availableBalance: number
  frozenBalance: number
  version?: number
}

const playerUserId = ref("")
const profile = ref<Player | null>(null)
const orders = ref<Order[]>([])
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
const loading = ref(false)

const activeOrders = computed(() =>
  orders.value.filter((order) =>
    ["ACCEPTED", "IN_SERVICE", "FINISH_REQUESTED"].includes(order.status)
  )
)

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const identities = await getDemoIdentities()
    playerUserId.value = identities.players[0]?.userId ?? ""
    if (!playerUserId.value) return

    const [nextProfile, nextOrders, nextWallet] = await Promise.all([
      request<Player>("/player/profile", { userId: playerUserId.value }),
      request<Order[]>("/player/orders", { userId: playerUserId.value }),
      request<Wallet>("/wallet", { userId: playerUserId.value })
    ])
    profile.value = nextProfile
    orders.value = nextOrders
    wallet.value = nextWallet
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

onShow(load)

function openPool() {
  uni.navigateTo({ url: "/pages-player/order-pool/index" })
}

async function toggleAvailability() {
  if (!profile.value || !playerUserId.value) return
  const next = profile.value.service_status === "AVAILABLE" ? "OFFLINE" : "AVAILABLE"
  try {
    profile.value = await request<Player>("/player/profile", {
      method: "PATCH",
      userId: playerUserId.value,
      data: { service_status: next }
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "状态更新失败",
      icon: "none"
    })
  }
}

async function startService(order: Order) {
  try {
    await request<Order>(`/player/orders/${order.id}/start`, {
      method: "POST",
      userId: playerUserId.value
    })
    uni.showToast({ title: "服务已开始", icon: "success" })
    await load()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "开始失败",
      icon: "none"
    })
  }
}

async function requestFinish(order: Order) {
  try {
    await request<Order>(`/player/orders/${order.id}/finish`, {
      method: "POST",
      userId: playerUserId.value
    })
    uni.showToast({ title: "已请求用户确认", icon: "success" })
    await load()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "操作失败",
      icon: "none"
    })
  }
}
</script>

<template>
  <view class="page">
    <view class="summary">
      <view class="topline">
        <view>
          <text class="label">可提现收益</text>
          <view class="amount">¥ {{ (wallet.availableBalance / 100).toFixed(2) }}</view>
        </view>
        <view
          class="status"
          :class="{ offline: profile?.service_status !== 'AVAILABLE' }"
          @click="toggleAvailability"
        >
          ● {{ profile?.service_status === "AVAILABLE" ? "接单中" : "已离线" }}
        </view>
      </view>

      <view class="stats">
        <view>
          <text class="num">{{ orders.length }}</text>
          <text class="name">我的订单</text>
        </view>
        <view>
          <text class="num">{{ activeOrders.length }}</text>
          <text class="name">待履约</text>
        </view>
        <view>
          <text class="num">{{ profile?.verification_status ?? "--" }}</text>
          <text class="name">认证状态</text>
        </view>
      </view>

      <button class="primary" @click="openPool">去抢单</button>
    </view>

    <view class="section-head">
      <text class="section-title">履约订单</text>
      <text class="refresh" @click="load">刷新</text>
    </view>

    <view v-if="orders.length === 0" class="empty">暂无已抢订单，去大厅看看。</view>

    <view v-for="order in orders" :key="order.id" class="order-card">
      <view class="order-head">
        <view>
          <view class="order-no">{{ order.order_no }}</view>
          <view class="order-status">{{ order.status }}</view>
        </view>
        <view class="income">¥{{ (order.player_amount / 100).toFixed(2) }}</view>
      </view>

      <button
        v-if="order.status === 'ACCEPTED'"
        class="action"
        @click="startService(order)"
      >
        开始服务
      </button>
      <button
        v-else-if="order.status === 'IN_SERVICE'"
        class="action"
        @click="requestFinish(order)"
      >
        请求结束
      </button>
      <view v-else-if="order.status === 'FINISH_REQUESTED'" class="waiting">
        等待用户确认完成
      </view>
      <view v-else-if="order.status === 'SETTLED'" class="settled">
        已结算到钱包
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; padding-bottom: 60rpx; }
.summary { padding: 36rpx; border-radius: 36rpx; background: #17171f; color: white; }
.topline { display: flex; justify-content: space-between; align-items: flex-start; }
.label { color: #aaaab4; font-size: 22rpx; }
.amount { margin-top: 12rpx; font-size: 54rpx; font-weight: 800; }
.status { padding: 12rpx 18rpx; border-radius: 999rpx; background: rgba(34,197,94,.14); color: #5ddb8b; font-size: 22rpx; }
.status.offline { background: rgba(255,255,255,.08); color: #aaaab4; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 44rpx; padding-top: 30rpx; border-top: 1rpx solid rgba(255,255,255,.08); }
.stats view { text-align: center; min-width: 0; }
.num { display: block; overflow: hidden; text-overflow: ellipsis; font-size: 26rpx; font-weight: 700; }
.name { display: block; margin-top: 8rpx; color: #aaaab4; font-size: 20rpx; }
.primary { margin-top: 34rpx; height: 88rpx; line-height: 88rpx; border-radius: 28rpx; background: #6c5ce7; color: white; font-size: 28rpx; font-weight: 700; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 38rpx 4rpx 20rpx; }
.section-title { font-size: 30rpx; font-weight: 750; }
.refresh { color: #6c5ce7; font-size: 22rpx; }
.empty { padding: 50rpx 24rpx; border-radius: 28rpx; background: #fff; color: #92929d; text-align: center; font-size: 24rpx; }
.order-card { margin-bottom: 20rpx; padding: 28rpx; border-radius: 30rpx; background: #fff; }
.order-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 20rpx; }
.order-no { font-size: 23rpx; font-weight: 700; }
.order-status { margin-top: 10rpx; color: #6c5ce7; font-size: 22rpx; }
.income { color: #6c5ce7; font-size: 30rpx; font-weight: 800; }
.action { margin-top: 24rpx; height: 74rpx; line-height: 74rpx; border-radius: 22rpx; background: #6c5ce7; color: #fff; font-size: 24rpx; font-weight: 700; }
.waiting, .settled { margin-top: 22rpx; padding: 20rpx; border-radius: 20rpx; background: #f5f3ff; color: #6c5ce7; text-align: center; font-size: 22rpx; }
.settled { background: #eafbf2; color: #22a665; }
</style>
