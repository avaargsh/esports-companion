<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"
import { ref } from "vue"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Order = {
  id: string
  order_no: string
  status: string
  total_amount: number
}

const orders = ref<Order[]>([])

onShow(async () => {
  const identities = await getDemoIdentities()
  orders.value = await request<Order[]>("/orders", {
    userId: identities.customer.userId
  })
})

function openOrder(id: string) {
  uni.navigateTo({ url: `/pages/order-detail/index?id=${id}` })
}
</script>

<template>
  <view class="page">
    <view v-if="orders.length === 0" class="empty">还没有订单，从首页选择游戏开始。</view>
    <view v-for="item in orders" :key="item.id" class="card" @click="openOrder(item.id)">
      <view>
        <view class="number">{{ item.order_no }}</view>
        <view class="status">{{ item.status }}</view>
      </view>
      <view class="amount">¥{{ (item.total_amount / 100).toFixed(2) }}</view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.empty { margin-top: 120rpx; text-align: center; color: #92929d; font-size: 24rpx; }
.card { margin-bottom: 20rpx; padding: 28rpx; border-radius: 30rpx; background: #fff; display: flex; align-items: center; justify-content: space-between; }
.number { font-size: 24rpx; font-weight: 700; }
.status { margin-top: 10rpx; color: #6c5ce7; font-size: 22rpx; }
.amount { font-size: 30rpx; font-weight: 800; }
</style>
