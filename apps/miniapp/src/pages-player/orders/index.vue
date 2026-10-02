<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import { listPlayerOrders } from "../../domain/order/api"
import { navigation } from "../../platform/navigation"
import { getPlayerPrincipal } from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import { isActiveOrder, orderStatusMeta } from "../../utils/order"

const orders = ref<Order[]>([])
const filter = ref<"ACTIVE" | "DONE">("ACTIVE")
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
const visibleOrders = computed(() =>
  orders.value.filter(item =>
    filter.value === "ACTIVE"
      ? isActiveOrder(item.status)
      : !isActiveOrder(item.status)
  )
)

async function load() {
  const hasContent = orders.value.length > 0
  if (hasContent) refreshing.value = true
  else startLoad()

  try {
    const principal = await getPlayerPrincipal()
    if (!principal) {
      orders.value = []
      finishLoad({ empty: true })
      return
    }

    orders.value = await listPlayerOrders(principal.userId)
    finishLoad({ empty: orders.value.length === 0 })
  } catch (error) {
    if (hasContent) {
      showMessage(
        error instanceof Error ? error.message : "服务订单刷新失败"
      )
    } else {
      failLoad(error, "服务订单加载失败")
    }
  } finally {
    refreshing.value = false
  }
}

function openOrder(id: string) {
  navigation.push("/pages-player/order-detail/index", { id })
}

onShow(() => {
  void load()
})
</script>

<template>
  <view class="page">
    <view class="heading">
      <view>
        <text class="eyebrow">服务管理</text>
        <text class="title">服务订单</text>
      </view>
      <text v-if="refreshing" class="refreshing">刷新中</text>
    </view>

    <view class="tabs">
      <text
        :class="{ active: filter === 'ACTIVE' }"
        @click="filter = 'ACTIVE'"
      >
        待履约 {{ activeCount }}
      </text>
      <text
        :class="{ active: filter === 'DONE' }"
        @click="filter = 'DONE'"
      >
        已结束 {{ doneCount }}
      </text>
    </view>

    <view v-if="loadStatus === 'loading'" class="list">
      <view v-for="n in 3" :key="n" class="order-skeleton"></view>
    </view>

    <view v-else-if="loadStatus === 'error'" class="state-card">
      <text class="state-icon">↻</text>
      <text class="state-title">服务订单暂时没加载出来</text>
      <text class="state-desc">{{ loadMessage }}</text>
      <text class="state-action" @click="load">重新加载</text>
    </view>

    <view v-else-if="!visibleOrders.length" class="empty">
      <view class="empty-icon">单</view>
      <text>
        {{ filter === "ACTIVE" ? "暂无待履约服务" : "暂无已结束服务" }}
      </text>
    </view>

    <view v-else class="list">
      <view
        v-for="item in visibleOrders"
        :key="item.id"
        class="card"
        @click="openOrder(item.id)"
      >
        <view class="card-top">
          <text class="number">{{ item.order_no }}</text>
          <text class="chevron">›</text>
        </view>
        <view class="card-main">
          <view>
            <text class="status">
              {{ orderStatusMeta(item.status, "PLAYER").label }}
            </text>
            <text class="status-desc">
              {{ orderStatusMeta(item.status, "PLAYER").description }}
            </text>
          </view>
          <view class="income">
            <text>本单收入</text>
            <b>
              <small>¥</small>{{ (item.player_amount / 100).toFixed(2) }}
            </b>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;background:var(--inverse-bg);color:#fff}.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:18rpx;padding:9rpx 2rpx 20rpx}.eyebrow,.title{display:block}.eyebrow{color:#6f6d79;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;font-size:36rpx;font-weight:850}.refreshing{padding-bottom:4rpx;color:#777582;font-size:17rpx}.tabs{display:inline-flex;gap:4rpx;margin-bottom:18rpx;padding:5rpx;border-radius:18rpx;background:var(--inverse-surface)}.tabs text{min-width:130rpx;padding:11rpx 16rpx;border-radius:14rpx;color:#777582;text-align:center;font-size:18rpx}.tabs .active{background:#2a2738;color:#fff;font-weight:750}
.list{display:flex;flex-direction:column;gap:12rpx}.order-skeleton{height:180rpx;border-radius:29rpx;background:var(--inverse-surface)}.card{padding:24rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:29rpx;background:var(--inverse-surface)}.card-top{display:flex;justify-content:space-between;gap:15rpx}.number{color:#696773;font-size:15rpx}.chevron{color:#575561;font-size:27rpx}.card-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:17rpx}.status,.status-desc{display:block}.status{font-size:25rpx;font-weight:790}.status-desc{margin-top:6rpx;color:#777582;font-size:16rpx}.income{text-align:right}.income>text{display:block;color:#777582;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#afa3fb;font-size:29rpx}.income small{font-size:16rpx}.empty,.state-card{padding:100rpx 20rpx;color:#777582;text-align:center;font-size:19rpx}.empty-icon,.state-icon{width:88rpx;height:88rpx;margin:0 auto 18rpx;display:flex;align-items:center;justify-content:center;border-radius:28rpx;background:var(--inverse-surface);color:#7f72d9;font-size:28rpx;font-weight:800}.state-title,.state-desc{display:block}.state-title{color:#d3d1da;font-size:24rpx;font-weight:760}.state-desc{max-width:500rpx;margin:8rpx auto 0;line-height:1.5}.state-action{display:inline-block;margin-top:18rpx;color:#a99df3;font-weight:750}
</style>
