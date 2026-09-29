<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import OrderCard from "../../components/OrderCard.vue"
import type { Order } from "../../types/domain"
import { isActiveOrder } from "../../utils/order"

type Filter = "all" | "active" | "done"

const orders = ref<Order[]>([])
const loading = ref(false)
const filter = ref<Filter>("all")

const visibleOrders = computed(() => {
  if (filter.value === "active") {
    return orders.value.filter(item => isActiveOrder(item.status))
  }
  if (filter.value === "done") {
    return orders.value.filter(item => !isActiveOrder(item.status))
  }
  return orders.value
})

async function load() {
  loading.value = true
  try {
    const identities = await getDemoIdentities()
    orders.value = await request<Order[]>("/orders?limit=50", {
      userId: identities.customer.userId
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "订单加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

onShow(() => { void load() })

function openOrder(order: Order) {
  uni.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })
}
</script>

<template>
  <view class="page">
    <view class="tabs">
      <text :class="{ active: filter === 'all' }" @click="filter = 'all'">全部</text>
      <text :class="{ active: filter === 'active' }" @click="filter = 'active'">进行中</text>
      <text :class="{ active: filter === 'done' }" @click="filter = 'done'">已结束</text>
    </view>

    <view v-if="loading" class="empty">订单加载中…</view>
    <view v-else-if="visibleOrders.length === 0" class="empty">
      <view class="empty-icon">单</view>
      <view class="empty-title">{{ orders.length ? "这个分类暂无订单" : "还没有订单" }}</view>
      <view class="empty-desc">从首页选择游戏，即可创建第一笔陪玩订单。</view>
    </view>

    <view v-else class="list">
      <OrderCard
        v-for="item in visibleOrders"
        :key="item.id"
        :order="item"
        @open="openOrder"
      />
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.tabs { display: flex; gap: 42rpx; padding: 8rpx 4rpx 30rpx; color: #92929d; font-size: 24rpx; }
.tabs text { position: relative; padding-bottom: 12rpx; }
.tabs .active { color: #15151b; font-weight: 700; }
.tabs .active::after { content: ""; position: absolute; left: 25%; right: 25%; bottom: 0; height: 5rpx; border-radius: 999rpx; background: #6c5ce7; }
.list { display: flex; flex-direction: column; gap: 18rpx; }
.empty { padding: 110rpx 20rpx; text-align: center; color: #92929d; font-size: 23rpx; }
.empty-icon { width: 110rpx; height: 110rpx; margin: 0 auto; border-radius: 34rpx; background: #f0edff; color: #6c5ce7; display: flex; align-items: center; justify-content: center; font-size: 38rpx; font-weight: 800; }
.empty-title { margin-top: 28rpx; color: #15151b; font-size: 30rpx; font-weight: 700; }
.empty-desc { margin-top: 12rpx; line-height: 1.6; }
</style>
