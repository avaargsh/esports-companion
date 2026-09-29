<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"
import { ref } from "vue"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Order = {
  id: string
  order_no: string
  status: string
  player_amount: number
}

const orders = ref<Order[]>([])

async function load() {
  const identities = await getDemoIdentities()
  const userId = identities.players[0]?.userId
  if (!userId) return
  orders.value = await request<Order[]>("/player/orders", { userId })
}

function openOrder(id: string) {
  uni.navigateTo({ url: `/pages-player/order-detail/index?id=${id}` })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view v-if="orders.length === 0" class="empty">暂无服务订单</view>
    <view v-for="item in orders" :key="item.id" class="card" @click="openOrder(item.id)">
      <view>
        <view class="number">{{ item.order_no }}</view>
        <view class="status">{{ item.status }}</view>
      </view>
      <view class="income">¥{{ (item.player_amount / 100).toFixed(2) }}</view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.empty { margin-top: 120rpx; color: #92929d; text-align: center; font-size: 24rpx; }
.card { margin-bottom: 20rpx; padding: 30rpx; border-radius: 30rpx; background: white; display: flex; align-items: center; justify-content: space-between; }
.number { font-size: 23rpx; font-weight: 700; }
.status { margin-top: 10rpx; color: #6c5ce7; font-size: 22rpx; }
.income { color: #15151b; font-size: 32rpx; font-weight: 800; }
</style>
