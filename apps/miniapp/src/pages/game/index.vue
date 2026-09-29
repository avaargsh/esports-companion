<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app"
import { ref } from "vue"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type SKU = {
  id: string
  game_id: string
  name: string
  service_type: string
  duration_minutes: number
  price: number
}

type Order = { id: string }

const gameId = ref("")
const gameName = ref("选择服务")
const skus = ref<SKU[]>([])
const creating = ref("")

onLoad(async (query) => {
  gameId.value = String(query?.id ?? "")
  gameName.value = decodeURIComponent(String(query?.name ?? "选择服务"))
  if (gameId.value) {
    skus.value = await request<SKU[]>(`/games/${gameId.value}/skus`)
  }
})

async function createOrder(sku: SKU) {
  if (creating.value) return
  creating.value = sku.id
  try {
    const identities = await getDemoIdentities()
    const order = await request<Order>("/orders", {
      method: "POST",
      userId: identities.customer.userId,
      data: { sku_id: sku.id, quantity: 1, remark: "Mini Program Demo" }
    })
    uni.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "下单失败", icon: "none" })
  } finally {
    creating.value = ""
  }
}
</script>

<template>
  <view class="page">
    <view class="title">{{ gameName }}</view>
    <view class="subtitle">选择服务套餐后创建订单</view>
    <view v-for="sku in skus" :key="sku.id" class="sku-card">
      <view>
        <view class="sku-name">{{ sku.name }}</view>
        <view class="meta">{{ sku.duration_minutes }} 分钟 · {{ sku.service_type }}</view>
      </view>
      <view class="right">
        <view class="price">¥{{ (sku.price / 100).toFixed(2) }}</view>
        <button class="buy" :loading="creating === sku.id" @click="createOrder(sku)">下单</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.title { font-size: 40rpx; font-weight: 800; }
.subtitle { margin-top: 10rpx; color: #92929d; font-size: 24rpx; }
.sku-card { margin-top: 24rpx; padding: 30rpx; border-radius: 30rpx; background: #fff; display: flex; justify-content: space-between; align-items: center; }
.sku-name { font-size: 28rpx; font-weight: 700; }
.meta { margin-top: 12rpx; color: #92929d; font-size: 22rpx; }
.right { text-align: right; }
.price { color: #6c5ce7; font-size: 32rpx; font-weight: 800; }
.buy { margin-top: 14rpx; width: 140rpx; height: 64rpx; line-height: 64rpx; border-radius: 20rpx; background: #6c5ce7; color: #fff; font-size: 22rpx; }
</style>
