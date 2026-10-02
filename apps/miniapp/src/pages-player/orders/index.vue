<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import { usePlayerOrders } from "../../features/player-workbench/usePlayerOrders"
import { navigation } from "../../platform/navigation"
import { orderStatusMeta } from "../../utils/order"

const {
  orders,
  filter,
  refreshing,
  loadStatus,
  loadMessage,
  activeCount,
  doneCount,
  visibleOrders,
  load
} = usePlayerOrders()

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

    <EmptyState
      v-else-if="loadStatus === 'error'"
      title="服务订单暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      inverse
      @action="load"
    />

    <EmptyState
      v-else-if="!visibleOrders.length"
      :title="filter === 'ACTIVE' ? '暂无待履约服务' : '暂无已结束服务'"
      :description="
        orders.length
          ? '切换分类查看其它服务订单'
          : '接单后，服务进度会统一出现在这里'
      "
      symbol="单"
      inverse
    />

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
            <b><small>¥</small>{{ (item.player_amount / 100).toFixed(2) }}</b>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;background:var(--inverse-bg);color:#fff}.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:18rpx;padding:9rpx 2rpx 20rpx}.eyebrow,.title{display:block}.eyebrow{color:#6f6d79;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;font-size:36rpx;font-weight:850}.refreshing{padding-bottom:4rpx;color:#777582;font-size:17rpx}.tabs{display:inline-flex;gap:4rpx;margin-bottom:18rpx;padding:5rpx;border-radius:18rpx;background:var(--inverse-surface)}.tabs text{min-width:130rpx;padding:11rpx 16rpx;border-radius:14rpx;color:#777582;text-align:center;font-size:18rpx}.tabs .active{background:#2a2738;color:#fff;font-weight:750}
.list{display:flex;flex-direction:column;gap:12rpx}.order-skeleton{height:180rpx;border-radius:29rpx;background:var(--inverse-surface)}.card{padding:24rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:29rpx;background:var(--inverse-surface)}.card-top{display:flex;justify-content:space-between;gap:15rpx}.number{color:#696773;font-size:15rpx}.chevron{color:#575561;font-size:27rpx}.card-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:17rpx}.status,.status-desc{display:block}.status{font-size:25rpx;font-weight:790}.status-desc{margin-top:6rpx;color:#777582;font-size:16rpx}.income{text-align:right}.income>text{display:block;color:#777582;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#afa3fb;font-size:29rpx}.income small{font-size:16rpx}
</style>
