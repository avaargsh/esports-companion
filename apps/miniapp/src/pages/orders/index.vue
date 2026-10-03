<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import EmptyState from "../../components/EmptyState.vue"
import OrderCard from "../../components/OrderCard.vue"
import { listCustomerOrders } from "../../domain/order/api"
import { navigation } from "../../platform/navigation"
import { getCustomerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import { isActiveOrder } from "../../utils/order"

type Filter = "all" | "active" | "done"

const orders = ref<Order[]>([])
const filter = ref<Filter>("all")
const refreshing = ref(false)
const {
  status: loadStatus,
  message: loadMessage,
  start: startLoad,
  succeed: finishLoad,
  fail: failLoad
} = useAsyncStatus("loading")

const activeCount = computed(() =>
  orders.value.filter(item => isActiveOrder(item.status)).length
)
const doneCount = computed(() => orders.value.length - activeCount.value)
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
  const hasContent = orders.value.length > 0
  if (hasContent) refreshing.value = true
  else startLoad()

  try {
    const principal = await getCustomerPrincipal()
    orders.value = await listCustomerOrders(principal.userId)
    finishLoad({ empty: orders.value.length === 0 })
  } catch (error) {
    if (hasContent) {
      showMessage(error instanceof Error ? error.message : "订单刷新失败")
    } else {
      failLoad(error, "订单加载失败")
    }
  } finally {
    refreshing.value = false
  }
}

onShow(() => {
  void load()
})

function openOrder(order: Order) {
  navigation.push("/pages/order-detail/index", { id: order.id })
}

function goHome() {
  navigation.tab("/pages/home/index")
}
</script>

<template>
  <view class="safe-page custom-safe-page orders-page">
    <view class="heading">
      <view>
        <text class="title">我的订单</text>
        <text class="subtitle">服务状态、售后与评价都在订单里处理。</text>
      </view>
      <text v-if="refreshing" class="refreshing">刷新中</text>
    </view>

    <view class="tabs">
      <view :class="['tab', { active: filter === 'all' }]" @click="filter = 'all'">
        <text>全部</text><b>{{ orders.length }}</b>
      </view>
      <view :class="['tab', { active: filter === 'active' }]" @click="filter = 'active'">
        <text>进行中</text><b>{{ activeCount }}</b>
      </view>
      <view :class="['tab', { active: filter === 'done' }]" @click="filter = 'done'">
        <text>已结束</text><b>{{ doneCount }}</b>
      </view>
    </view>

    <view v-if="loadStatus === 'loading'" class="list">
      <view v-for="n in 4" :key="n" class="skeleton order-skeleton"></view>
    </view>

    <EmptyState
      v-else-if="loadStatus === 'error'"
      title="订单暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      inverse
      @action="load"
    />

    <EmptyState
      v-else-if="visibleOrders.length === 0"
      :title="orders.length ? '这个分类暂无订单' : '还没有订单'"
      :description="orders.length ? '切换分类查看其它订单' : '从首页选游戏，即可创建第一笔陪玩订单'"
      :action="orders.length ? '' : '去下单'"
      symbol="单"
      inverse
      @action="goHome"
    />

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
.orders-page{min-height:100vh;background:#f7f7f8;color:#111827}.heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx;padding:12rpx 3rpx 28rpx}.title{display:block;color:#111827;font-size:40rpx;font-weight:900}.subtitle{display:block;margin-top:8rpx;color:#6b7280;font-size:20rpx}.refreshing{padding:8rpx 13rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:999rpx;background:rgba(0,0,0,.06);color:#111827;font-size:17rpx;white-space:nowrap}.tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:7rpx;margin-bottom:24rpx;padding:7rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:26rpx;background:#ffffff;box-shadow:0 10rpx 30rpx rgba(0,0,0,.12)}.tab{height:66rpx;display:flex;align-items:center;justify-content:center;gap:8rpx;border-radius:21rpx;color:#6b7280;font-size:19rpx;font-weight:780}.tab b{font-size:18rpx}.tab.active{background:linear-gradient(135deg,#111827,#000000);color:#fff;box-shadow:0 12rpx 28rpx rgba(0,0,0,.16)}.list{display:flex;flex-direction:column;gap:16rpx}.order-skeleton{height:240rpx;border-radius:32rpx;background:#ffffff;border:1rpx solid rgba(0,0,0,.08)}
</style>
