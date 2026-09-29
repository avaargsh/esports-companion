<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getRuntimeIdentities } from "../../api/identity"
import type { Order } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"

const orders = ref<Order[]>([])

async function load() {
  const identities = await getRuntimeIdentities()
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
    <view v-if="orders.length === 0" class="empty">暂无待履约服务订单</view>
    <view
      v-for="item in orders"
      :key="item.id"
      class="card"
      @click="openOrder(item.id)"
    >
      <view>
        <view class="number">{{ item.order_no }}</view>
        <view class="status">{{ orderStatusMeta(item.status).label }}</view>
      </view>
      <view class="income">
        <text>本单收入</text>
        <b>¥{{ (item.player_amount / 100).toFixed(2) }}</b>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 28rpx; background: #0f0f15; box-sizing: border-box; }
.empty { margin-top: 120rpx; color: #777784; text-align: center; font-size: 24rpx; }
.card { margin-bottom: 18rpx; padding: 30rpx; border-radius: 30rpx; background: #181820; color: #fff; display: flex; align-items: center; justify-content: space-between; }
.number { color: #aaaab4; font-size: 21rpx; }
.status { margin-top: 10rpx; font-size: 29rpx; font-weight: 700; }
.income { text-align: right; }
.income text { display: block; color: #777784; font-size: 18rpx; }
.income b { display: block; margin-top: 6rpx; color: #9f91ff; font-size: 31rpx; }
</style>
