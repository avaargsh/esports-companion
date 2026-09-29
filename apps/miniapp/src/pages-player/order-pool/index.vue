<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Game, Order } from "../../types/domain"

const games = ref<Game[]>([])
const gameId = ref("")
const orders = ref<Order[]>([])
const playerUserId = ref("")
const loading = ref(false)

async function loadPool() {
  if (!gameId.value) return
  loading.value = true
  try {
    orders.value = await request<Order[]>(`/player/order-pool?game_id=${gameId.value}`)
  } finally {
    loading.value = false
  }
}

onShow(async () => {
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  games.value = await request<Game[]>("/games")
  if (!gameId.value && games.value.length) {
    gameId.value = games.value[0].id
  }
  await loadPool()
})

async function selectGame(id: string) {
  gameId.value = id
  await loadPool()
}

async function claim(order: Order) {
  if (!playerUserId.value) {
    uni.showToast({ title: "未找到 Demo Player", icon: "none" })
    return
  }

  try {
    const claimed = await request<Order>(
      `/player/orders/${order.id}/claim`,
      {
        method: "POST",
        userId: playerUserId.value,
        data: { expected_version: order.version }
      }
    )
    uni.showToast({ title: "接单成功", icon: "success" })
    uni.navigateTo({
      url: `/pages-player/order-detail/index?id=${claimed.id}`
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "接单失败",
      icon: "none"
    })
    await loadPool()
  }
}
</script>

<template>
  <view class="page">
    <scroll-view scroll-x class="filter">
      <view class="filter-row">
        <text
          v-for="game in games"
          :key="game.id"
          :class="{ active: gameId === game.id }"
          @click="selectGame(game.id)"
        >
          {{ game.name }}
        </text>
      </view>
    </scroll-view>

    <view class="pool-head">
      <text>实时订单池</text>
      <text class="refresh" @click="loadPool">刷新</text>
    </view>

    <view v-if="loading" class="empty">订单池加载中…</view>
    <view v-else-if="orders.length === 0" class="empty">当前没有待抢订单。</view>

    <view v-for="order in orders" :key="order.id" class="order-card">
      <view class="head">
        <view>
          <view class="game">即时陪玩订单</view>
          <view class="meta">订单 {{ order.order_no }} · 版本 {{ order.version }}</view>
        </view>
        <view class="income">¥{{ (order.player_amount / 100).toFixed(2) }}</view>
      </view>

      <view class="tags">
        <text>平台担保</text>
        <text>并发抢单保护</text>
      </view>

      <button class="claim" @click="claim(order)">立即抢单</button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.filter { width: 100%; }
.filter-row { display: flex; gap: 30rpx; padding: 8rpx 4rpx 24rpx; white-space: nowrap; }
.filter-row text { flex: none; color: #92929d; font-size: 24rpx; }
.filter-row .active { color: #15151b; font-weight: 700; }
.pool-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20rpx; font-size: 31rpx; font-weight: 700; }
.refresh { color: #6c5ce7; font-size: 21rpx; font-weight: 500; }
.empty { padding: 80rpx 20rpx; text-align: center; color: #92929d; font-size: 23rpx; }
.order-card { margin-bottom: 20rpx; padding: 30rpx; border-radius: 32rpx; background: #fff; box-shadow: 0 12rpx 40rpx rgba(25,20,60,.05); }
.head { display: flex; justify-content: space-between; gap: 20rpx; }
.game { font-size: 29rpx; font-weight: 700; }
.meta { margin-top: 10rpx; color: #92929d; font-size: 20rpx; }
.income { color: #6c5ce7; font-size: 36rpx; font-weight: 800; }
.tags { display: flex; gap: 12rpx; margin-top: 24rpx; }
.tags text { padding: 8rpx 14rpx; border-radius: 999rpx; background: #f5f3ff; color: #6c5ce7; font-size: 19rpx; }
.claim { margin-top: 26rpx; height: 82rpx; line-height: 82rpx; border-radius: 26rpx; background: #6c5ce7; color: #fff; font-size: 26rpx; font-weight: 700; }
</style>
