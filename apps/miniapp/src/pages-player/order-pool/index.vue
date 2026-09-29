<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"
import { ref } from "vue"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Game = { id: string; name: string }
type Order = {
  id: string
  status: string
  total_amount: number
  player_amount: number
  version: number
}

const games = ref<Game[]>([])
const gameId = ref("")
const orders = ref<Order[]>([])
const playerUserId = ref("")

async function loadPool() {
  if (!gameId.value) return
  orders.value = await request<Order[]>(`/player/order-pool?game_id=${gameId.value}`)
}

onShow(async () => {
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  games.value = await request<Game[]>("/games")
  if (!gameId.value && games.value.length) gameId.value = games.value[0].id
  await loadPool()
})

async function selectGame(id: string) {
  gameId.value = id
  await loadPool()
}

async function claim(order: Order) {
  if (!playerUserId.value) return
  try {
    const claimed = await request<Order>(`/player/orders/${order.id}/claim`, {
      method: "POST",
      userId: playerUserId.value,
      data: { expected_version: order.version }
    })
    uni.showToast({ title: "抢单成功", icon: "success" })
    uni.navigateTo({ url: `/pages-player/order-detail/index?id=${claimed.id}` })
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "抢单失败", icon: "none" })
    await loadPool()
  }
}
</script>

<template>
  <view class="page">
    <scroll-view scroll-x class="filter">
      <text
        v-for="game in games"
        :key="game.id"
        :class="{ active: gameId === game.id }"
        @click="selectGame(game.id)"
      >{{ game.name }}</text>
    </scroll-view>

    <view v-if="orders.length === 0" class="empty">当前没有待抢订单。</view>
    <view v-for="order in orders" :key="order.id" class="order-card">
      <view class="head">
        <view>
          <view class="game">待抢服务订单</view>
          <view class="meta">版本 {{ order.version }} · {{ order.status }}</view>
        </view>
        <view class="income">¥{{ (order.player_amount / 100).toFixed(2) }}</view>
      </view>
      <button class="claim" @click="claim(order)">立即抢单</button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.filter { white-space: nowrap; padding: 10rpx 0 28rpx; }
.filter text { display: inline-block; margin-right: 28rpx; color: #92929d; font-size: 24rpx; }
.filter .active { color: #6c5ce7; font-weight: 700; }
.empty { padding: 60rpx 20rpx; text-align: center; color: #92929d; font-size: 24rpx; }
.order-card { margin-bottom: 22rpx; padding: 30rpx; border-radius: 32rpx; background: #fff; box-shadow: 0 12rpx 40rpx rgba(25,20,60,.06); }
.head { display: flex; justify-content: space-between; gap: 20rpx; }
.game { font-size: 30rpx; font-weight: 700; }
.meta { margin-top: 10rpx; color: #92929d; font-size: 22rpx; }
.income { color: #6c5ce7; font-size: 38rpx; font-weight: 800; }
.claim { margin-top: 28rpx; height: 82rpx; line-height: 82rpx; border-radius: 26rpx; background: #6c5ce7; color: #fff; font-size: 26rpx; font-weight: 700; }
</style>
