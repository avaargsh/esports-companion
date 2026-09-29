<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import OrderCard from "../../components/OrderCard.vue"
import type { Order } from "../../types/domain"
import { isActiveOrder } from "../../utils/order"

const orders = ref<Order[]>([])
const loading = ref(false)
const activeTab = ref<"ALL" | "ACTIVE" | "DONE">("ALL")

const tabs = [
  { key: "ALL" as const, label: "全部" },
  { key: "ACTIVE" as const, label: "进行中" },
  { key: "DONE" as const, label: "已完成" }
]

const filtered = computed(() => {
  if (activeTab.value === "ACTIVE") {
    return orders.value.filter(item => isActiveOrder(item.status))
  }
  if (activeTab.value === "DONE") {
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

function open(order: Order) {
  uni.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })
}

function goHome() {
  uni.switchTab({ url: "/pages/home/index" })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="heading">
      <view><text class="eyebrow">MY ORDERS</text><view class="title">订单中心</view></view>
      <view class="count">{{ orders.length }}</view>
    </view>

    <view class="tabs">
      <view v-for="tab in tabs" :key="tab.key" class="tab" :class="{active:activeTab===tab.key}" @click="activeTab=tab.key">
        {{ tab.label }}
      </view>
    </view>

    <view v-if="loading" class="empty">正在同步订单…</view>
    <view v-else-if="!filtered.length" class="empty-state">
      <view class="icon">✦</view>
      <view class="empty-title">{{ orders.length ? "这个分类还没有订单" : "还没有订单" }}</view>
      <view class="desc">从首页选择游戏和服务规格，创建你的第一笔陪玩订单。</view>
      <button v-if="!orders.length" class="primary" @click="goHome">去逛逛</button>
    </view>

    <view v-else class="list">
      <OrderCard
        v-for="order in filtered"
        :key="order.id"
        :order="order"
        @open="open"
      />
    </view>
  </view>
</template>

<style scoped>
.page { padding:28rpx; }
.heading { display:flex; align-items:flex-end; justify-content:space-between; padding:12rpx 2rpx 26rpx; }
.eyebrow { color:#a0a0aa; font-size:18rpx; letter-spacing:3rpx; }
.title { margin-top:6rpx; font-size:38rpx; font-weight:850; }
.count { min-width:54rpx; height:54rpx; padding:0 14rpx; display:flex; align-items:center; justify-content:center; border-radius:18rpx; background:#17171f; color:#fff; font-size:20rpx; font-weight:700; }
.tabs { display:flex; gap:12rpx; margin-bottom:24rpx; padding:6rpx; border-radius:24rpx; background:#ececf3; }
.tab { flex:1; height:62rpx; display:flex; align-items:center; justify-content:center; border-radius:18rpx; color:#8b8b96; font-size:22rpx; }
.tab.active { background:#fff; color:#1b1b22; font-weight:750; box-shadow:0 5rpx 16rpx rgba(25,20,60,.05); }
.list { display:flex; flex-direction:column; gap:18rpx; }
.empty { padding:120rpx 0; text-align:center; color:#92929d; font-size:22rpx; }
.empty-state { padding:110rpx 36rpx; text-align:center; }
.icon { width:116rpx; height:116rpx; margin:auto; border-radius:36rpx; background:#f0edff; color:#6c5ce7; display:flex; align-items:center; justify-content:center; font-size:42rpx; font-weight:850; }
.empty-title { margin-top:28rpx; color:#17171e; font-size:31rpx; font-weight:800; }
.desc { max-width:500rpx; margin:12rpx auto 0; color:#9898a2; font-size:22rpx; line-height:1.65; }
.primary { margin:30rpx auto 0; width:230rpx; height:74rpx; line-height:74rpx; border-radius:22rpx; background:#17171f; color:#fff; font-size:23rpx; }
</style>
