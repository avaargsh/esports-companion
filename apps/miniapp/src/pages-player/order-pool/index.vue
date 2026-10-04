<script setup lang="ts">
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import SampleJourney from "../../components/SampleJourney.vue"
import { usePlayerOrderPool } from "../../features/player-workbench/usePlayerOrderPool"
import { navigation } from "../../platform/navigation"
import { stopPullDownRefresh } from "../../platform/page"
import type { Order } from "../../types/domain"

const {
  games,
  gameId,
  orders,
  claimingId,
  demoMode,
  loadStatus,
  loadMessage,
  bestIncome,
  claimBlockReason,
  acceptingOrders,
  canClaim,
  bootstrap,
  refresh,
  loadPool,
  selectGame,
  claim
} = usePlayerOrderPool()

const uiIcons = {
  empty: "https://img.icons8.com/fluency/96/open-box.png"
}

function backToWorkbench() {
  navigation.back()
}

async function claimAndOpen(order: Order) {
  const claimed = await claim(order)
  if (!claimed) return
  navigation.push("/pages-player/order-detail/index", { id: claimed.id })
}

onShow(() => {
  void bootstrap()
})

onPullDownRefresh(async () => {
  await refresh()
  stopPullDownRefresh()
})
</script>

<template>
  <view class="page">
    <view class="heading">
      <view>
        <text class="eyebrow">接单市场</text>
        <text class="title">抢单大厅</text>
      </view>
      <view class="live"><text class="pulse"></text>{{ acceptingOrders ? "可接单" : "暂停" }}</view>
    </view>

    <SampleJourney
      v-if="demoMode"
      :step="3"
      role="陪玩端"
      title="找到刚才支付的订单"
      description="只展示与你已启用服务匹配的公开订单。点击「立即抢单」进入履约。"
      dark
    />

    <view v-if="claimBlockReason" class="guard">
      <text>{{ claimBlockReason }}</text>
      <text class="guard-link" @click="backToWorkbench">去工作台 ›</text>
    </view>

    <view class="overview">
      <view><b>{{ orders.length }}</b><text>可抢订单</text></view>
      <view><b>¥{{ (bestIncome/100).toFixed(0) }}</b><text>最高单笔收入</text></view>
    </view>

    <scroll-view scroll-x class="filter" :show-scrollbar="false">
      <view class="filter-row">
        <text v-for="game in games" :key="game.id" :class="{active:gameId===game.id}" @click="selectGame(game.id)">
          {{ game.name }}
        </text>
      </view>
    </scroll-view>

    <view v-if="loadStatus === 'loading'" class="list">
      <view v-for="n in 3" :key="n" class="order-skeleton"></view>
    </view>

    <EmptyState
      v-else-if="loadStatus === 'error'"
      title="抢单大厅暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      inverse
      @action="bootstrap"
    />

    <view v-else-if="!orders.length" class="empty">
      <view class="empty-icon"><image :src="uiIcons.empty" mode="aspectFit" /></view>
      <text class="empty-title">现在没有可接订单</text>
      <text class="empty-desc">只展示与你已启用服务匹配的订单，下拉即可刷新。</text>
      <button class="ghost" @click="() => loadPool()">刷新订单</button>
    </view>

    <view v-else class="list">
      <view v-for="order in orders" :key="order.id" class="order-card">
        <view class="order-top">
          <view class="trust"><text class="trust-dot"></text>平台担保</view>
          <text class="order-no">{{ order.order_no }}</text>
        </view>
        <view class="order-main">
          <view>
            <text class="order-title">待接服务</text>
            <text class="order-meta">数量 × {{ order.quantity || 1 }}</text>
          </view>
          <view class="income">
            <text>预计收入</text>
            <b><small>¥</small>{{ (order.player_amount/100).toFixed(2) }}</b>
          </view>
        </view>
        <view class="amount-row">
          <text>服务数量 × {{ order.quantity || 1 }}</text>
          <text>订单总额 ¥{{ (order.total_amount/100).toFixed(2) }}</text>
        </view>
        <button class="claim" :disabled="!canClaim(order)||!!claimingId" @click="claimAndOpen(order)">
          {{ claimingId===order.id ? "正在抢单…" : canClaim(order) ? "立即抢单" : "暂不可接单" }}
        </button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;padding-bottom:calc(42rpx + env(safe-area-inset-bottom));background:#f7f7f8;color:#111827}.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;padding:9rpx 2rpx 23rpx}.eyebrow,.title{display:block}.eyebrow{color:#111827;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;color:#111827;font-size:36rpx;font-weight:850}.live{display:flex;align-items:center;gap:8rpx;padding:9rpx 13rpx;border:1rpx solid rgba(0,0,0,.09);border-radius:999rpx;background:rgba(0,0,0,.06);color:#111827;font-size:17rpx;font-weight:700}.pulse{width:10rpx;height:10rpx;border-radius:50%;background:currentColor;box-shadow:0 0 16rpx currentColor}.guard{display:flex;justify-content:space-between;gap:14rpx;margin-bottom:14rpx;padding:16rpx 18rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:19rpx;background:rgba(0,0,0,.06);color:#111827;font-size:17rpx}.guard-link{flex:none;color:#111827;font-weight:700}.overview{display:grid;grid-template-columns:1fr 1fr;gap:10rpx;margin-bottom:18rpx}.overview view{padding:20rpx 22rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:23rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.overview b,.overview text{display:block}.overview b{color:#111827;font-size:27rpx}.overview view:first-child b{color:#111827}.overview text{margin-top:5rpx;color:#6b7280;font-size:16rpx}.filter{width:100%;margin-bottom:18rpx}.filter-row{display:flex;gap:8rpx;white-space:nowrap}.filter-row text{flex:none;padding:12rpx 18rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:17rpx;background:#ffffff;color:#6b7280;font-size:18rpx}.filter-row text.active{border-color:rgba(0,0,0,.20);background:linear-gradient(135deg,#111827,#000000);color:#fff;font-weight:750}.list{display:flex;flex-direction:column;gap:13rpx}.order-skeleton{height:250rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff}.order-card{padding:25rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.order-top{display:flex;align-items:center;justify-content:space-between;gap:15rpx}.trust{display:flex;align-items:center;gap:7rpx;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(0,0,0,.06);color:#111827;font-size:15rpx;font-weight:700}.trust-dot{width:8rpx;height:8rpx;border-radius:50%;background:currentColor;box-shadow:0 0 14rpx currentColor}.order-no{max-width:330rpx;overflow:hidden;color:#6b7280;font-size:15rpx;text-overflow:ellipsis;white-space:nowrap}.order-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:22rpx}.order-title,.order-meta{display:block}.order-title{color:#111827;font-size:26rpx;font-weight:790}.order-meta{margin-top:6rpx;color:#6b7280;font-size:17rpx}.income{text-align:right}.income>text{display:block;color:#6b7280;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#111827;font-size:31rpx}.income small{font-size:17rpx}.amount-row{display:flex;justify-content:space-between;gap:16rpx;margin-top:21rpx;padding-top:17rpx;border-top:1rpx solid rgba(0,0,0,.06);color:#6b7280;font-size:16rpx}.claim{margin-top:18rpx;height:76rpx;line-height:76rpx;border-radius:22rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;font-size:22rpx;font-weight:770;box-shadow:0 16rpx 34rpx rgba(0,0,0,.12)}.claim[disabled]{background:#f3f4f6;color:#6b7280;opacity:1;box-shadow:none}.empty{padding:80rpx 24rpx;text-align:center}.empty-icon{width:94rpx;height:94rpx;margin:auto;display:flex;align-items:center;justify-content:center;border:1rpx solid rgba(0,0,0,.10);border-radius:30rpx;background:#ffffff;box-shadow:0 0 30rpx rgba(0,0,0,.08)}.empty-icon image{width:58rpx;height:58rpx}.empty-title,.empty-desc{display:block}.empty-title{margin-top:21rpx;color:#111827;font-size:26rpx;font-weight:780}.empty-desc{margin:9rpx auto 0;max-width:500rpx;color:#6b7280;font-size:18rpx;line-height:1.55}.ghost{width:210rpx;height:68rpx;margin:23rpx auto 0;line-height:68rpx;border-radius:20rpx;background:#f3f4f6;color:#111827;font-size:19rpx;border:1rpx solid rgba(0,0,0,.09)}
</style>
