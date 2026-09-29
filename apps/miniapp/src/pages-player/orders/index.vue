<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import PriceText from "../../components/PriceText.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Order } from "../../types/domain"
import { isActiveOrder, playerActionErrorMessage } from "../../utils/order"

const orders = ref<Order[]>([])
const loading = ref(false)
const filter = ref<"ACTIVE" | "DONE">("ACTIVE")

const visibleOrders = computed(() =>
  orders.value.filter(item =>
    filter.value === "ACTIVE"
      ? isActiveOrder(item.status)
      : !isActiveOrder(item.status)
  )
)

async function load() {
  loading.value = true
  try {
    const identities = await getDemoIdentities()
    const userId = identities.players[0]?.userId
    if (!userId) throw new Error("PLAYER_PROFILE_NOT_FOUND")
    orders.value = await request<Order[]>("/player/orders", { userId })
  } catch (error) {
    uni.showToast({
      title: playerActionErrorMessage(error instanceof Error ? error.message : ""),
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

function openOrder(id: string) {
  uni.navigateTo({ url: `/pages-player/order-detail/index?id=${id}` })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="heading">
      <view>
        <text class="eyebrow">FULFILLMENT</text>
        <view class="title">服务订单</view>
      </view>
      <text class="count">{{ visibleOrders.length }}</text>
    </view>

    <view class="tabs">
      <view :class="{ active: filter === 'ACTIVE' }" @click="filter = 'ACTIVE'">待履约</view>
      <view :class="{ active: filter === 'DONE' }" @click="filter = 'DONE'">已结束</view>
    </view>

    <view v-if="loading" class="empty">正在同步服务订单…</view>
    <view v-else-if="visibleOrders.length === 0" class="empty">
      {{ filter === "ACTIVE" ? "暂无待履约服务订单" : "暂无已结束服务订单" }}
    </view>

    <view
      v-for="item in visibleOrders"
      :key="item.id"
      class="card"
      @click="openOrder(item.id)"
    >
      <view class="left">
        <StatusTag :status="item.status" role="PLAYER" />
        <view class="number">{{ item.order_no }}</view>
        <view class="hint">数量 × {{ item.quantity || 1 }}</view>
      </view>
      <view class="income">
        <text>本单收入</text>
        <PriceText :cents="item.player_amount" size="md" />
        <text class="open">详情 ›</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#0f0f15; box-sizing:border-box; color:#fff; }
.heading { display:flex; align-items:flex-end; justify-content:space-between; padding:12rpx 2rpx 24rpx; }
.eyebrow { color:#666672; font-size:17rpx; letter-spacing:3rpx; }
.title { margin-top:7rpx; font-size:37rpx; font-weight:850; }
.count { min-width:50rpx; height:50rpx; padding:0 12rpx; display:flex; align-items:center; justify-content:center; border-radius:16rpx; background:#23232c; color:#aaaab5; font-size:18rpx; }
.tabs { display:flex; gap:10rpx; margin-bottom:20rpx; padding:6rpx; border-radius:22rpx; background:#191920; }
.tabs view { flex:1; height:60rpx; display:flex; align-items:center; justify-content:center; border-radius:17rpx; color:#777783; font-size:21rpx; }
.tabs .active { background:#292632; color:#fff; font-weight:750; }
.empty { padding:100rpx 20rpx; color:#777784; text-align:center; font-size:22rpx; }
.card { margin-bottom:16rpx; padding:28rpx; border:1rpx solid rgba(255,255,255,.05); border-radius:30rpx; background:#181820; display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.left { min-width:0; }
.number { margin-top:14rpx; overflow:hidden; color:#aaaab4; font-size:20rpx; white-space:nowrap; text-overflow:ellipsis; }
.hint { margin-top:7rpx; color:#666672; font-size:18rpx; }
.income { flex:none; text-align:right; }
.income>text:first-child { display:block; margin-bottom:4rpx; color:#777784; font-size:17rpx; }
.open { display:block; margin-top:8rpx; color:#8f81eb; font-size:18rpx; }
</style>
