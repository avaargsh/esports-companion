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

const uiIcons = {
  empty: "https://img.icons8.com/fluency/96/purchase-order.png"
}

function openOrder(id: string) {
  navigation.push("/pages-player/order-detail/index", { id })
}

function goPool() {
  navigation.push("/pages-player/order-pool/index")
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

    <view v-else-if="!visibleOrders.length" class="empty-orders">
      <view class="empty-figure"><image :src="uiIcons.empty" mode="aspectFit" /></view>
      <text class="empty-title">{{ filter === 'ACTIVE' ? '暂无待履约服务' : '暂无已结束服务' }}</text>
      <text class="empty-desc">{{ orders.length ? '切换分类查看其它服务订单' : '去抢单大厅接下第一单，服务进度会统一出现在这里' }}</text>
      <button v-if="!orders.length" class="empty-action" @click="goPool">去抢单大厅</button>
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
            <b><small>¥</small>{{ (item.player_amount / 100).toFixed(2) }}</b>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;background:#f7f7f8;color:#111827}.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:18rpx;padding:9rpx 2rpx 20rpx}.eyebrow,.title{display:block}.eyebrow{color:#111827;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;color:#111827;font-size:36rpx;font-weight:850}.refreshing{padding-bottom:4rpx;color:#6b7280;font-size:17rpx}.tabs{display:inline-flex;gap:5rpx;margin-bottom:18rpx;padding:6rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:18rpx;background:#ffffff}.tabs text{min-width:130rpx;padding:11rpx 16rpx;border-radius:14rpx;color:#6b7280;text-align:center;font-size:18rpx}.tabs .active{background:linear-gradient(135deg,#111827,#000000);color:#fff;font-weight:750;box-shadow:0 10rpx 24rpx rgba(0,0,0,.12)}.list{display:flex;flex-direction:column;gap:12rpx}.order-skeleton{height:180rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:29rpx;background:#ffffff}.empty-orders{padding:82rpx 28rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff;text-align:center;box-shadow:0 10rpx 30rpx rgba(0,0,0,.35)}.empty-figure{width:96rpx;height:96rpx;margin:0 auto;display:flex;align-items:center;justify-content:center;border-radius:30rpx;background:linear-gradient(135deg,rgba(0,0,0,.09),rgba(0,0,0,.05));box-shadow:0 0 34rpx rgba(0,0,0,.08)}.empty-figure image{width:58rpx;height:58rpx}.empty-title,.empty-desc{display:block}.empty-title{margin-top:20rpx;color:#111827;font-size:26rpx;font-weight:850}.empty-desc{max-width:520rpx;margin:9rpx auto 0;color:#6b7280;font-size:18rpx;line-height:1.55}.empty-action{width:230rpx;height:70rpx;margin:24rpx auto 0;line-height:70rpx;border-radius:22rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;font-size:20rpx;font-weight:850}.card{padding:24rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:29rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.card-top{display:flex;justify-content:space-between;gap:15rpx}.number{color:#6b7280;font-size:15rpx}.chevron{color:#111827;font-size:27rpx}.card-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:17rpx}.status,.status-desc{display:block}.status{color:#111827;font-size:25rpx;font-weight:790}.status-desc{margin-top:6rpx;color:#6b7280;font-size:16rpx}.income{text-align:right}.income>text{display:block;color:#6b7280;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#111827;font-size:29rpx}.income small{font-size:16rpx}
</style>
