<script setup lang="ts">
import { onLoad, onShow, onUnload } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import OrderChat from "../../components/OrderChat.vue"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import SampleJourney from "../../components/SampleJourney.vue"
import StatusTag from "../../components/StatusTag.vue"
import UiButton from "../../components/ui/UiButton.vue"
import { usePlayerOrderDetail } from "../../features/order-detail/usePlayerOrderDetail"

const {
  order,
  events,
  eventsExpanded,
  playerUserId,
  socketConnected,
  busy,
  aftercareReason,
  chatRefreshKey,
  demoMode,
  loadStatus,
  loadMessage,
  meta,
  incomeCaption,
  demoJourney,
  visibleEvents,
  chatVisible,
  chatWritable,
  primaryAction,
  canOpenDispute,
  init,
  refresh,
  retry,
  dispose,
  runPrimary,
  openDispute,
  eventTitle,
  actorLabel,
  formatTime
} = usePlayerOrderDetail()

onLoad(async query => {
  await init(String(query?.id ?? ""))
})

onShow(() => {
  void refresh()
})

onUnload(() => {
  dispose()
})
</script>

<template>
  <view class="page">
    <view v-if="loadStatus === 'loading'" class="loading">
      正在同步服务单…
    </view>

    <EmptyState
      v-else-if="loadStatus === 'error'"
      title="服务单暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      @action="retry"
    />

    <template v-else-if="order && meta">
      <SampleJourney
        v-if="demoMode && demoJourney"
        :step="demoJourney.step"
        role="陪玩端"
        :title="demoJourney.title"
        :description="demoJourney.description"
        dark
      />

      <view class="hero">
        <view class="hero-top">
          <StatusTag :status="order.status" role="PLAYER" />
          <text class="order-no">{{ order.order_no }}</text>
        </view>
        <view class="income"><PriceText :cents="order.player_amount" size="lg" /></view>
        <view class="caption">{{ incomeCaption }}</view>
        <view class="state-desc">{{ meta.description }}</view>
        <OrderProgress :status="order.status" role="PLAYER" dark />
      </view>

      <view class="card">
        <view><text>用户实付</text><PriceText :cents="order.total_amount" size="sm" /></view>
        <view><text>平台服务费</text><PriceText :cents="order.platform_fee" size="sm" muted /></view>
        <view><text>服务数量</text><text class="value">× {{ order.quantity || 1 }}</text></view>
      </view>

      <view v-if="events.length" class="card timeline-card">
        <view class="card-title-row">
          <view class="card-title">服务进展</view>
          <text v-if="events.length > 4" class="card-action" @click="eventsExpanded = !eventsExpanded">
            {{ eventsExpanded ? "收起" : "全部 " + events.length + " 条" }}
          </text>
        </view>
        <view v-for="(event,index) in visibleEvents" :key="event.id" class="event">
          <view class="track">
            <view class="event-dot" :class="{ latest:index===visibleEvents.length-1 }"></view>
            <view v-if="index < visibleEvents.length-1" class="event-line"></view>
          </view>
          <view class="event-copy">
            <view class="event-head">
              <text>{{ eventTitle(event) }}</text>
              <text class="time">{{ formatTime(event.created_at) }}</text>
            </view>
            <text class="actor">{{ actorLabel(event.actor_type) }}</text>
          </view>
        </view>
      </view>

      <view v-if="!socketConnected" class="realtime offline">
        <view>
          <text class="live-dot">●</text>
          自动更新暂时中断
        </view>
        <text class="refresh" @click="refresh">刷新</text>
      </view>

      <OrderChat
        v-if="chatVisible"
        :order-id="order.id"
        :user-id="playerUserId"
        :refresh-key="chatRefreshKey"
        :writable="chatWritable"
        dark
      />

      <view v-if="canOpenDispute" class="card aftercare-card">
        <view class="card-title">履约异常？</view>
        <text class="aftercare-hint">
          无法继续服务、用户失联或服务存在争议时，可申请平台介入。
        </text>
        <textarea
          v-model="aftercareReason"
          maxlength="500"
          placeholder="简单说明情况，便于平台处理"
        />
        <view class="aftercare-action">
          <UiButton
            variant="secondary"
            inverse
            :disabled="busy"
            @click="openDispute"
          >
            申请平台介入
          </UiButton>
        </view>
      </view>

      <view v-if="order.status === 'FINISH_REQUESTED'" class="notice">
        已申请完成，正在等待用户确认；超时后由后端自动确认流程处理。
      </view>
      <view v-else-if="order.status === 'SETTLED'" class="notice success">
        本单已完成结算，收入已计入可用收益。
      </view>
      <view v-else-if="order.status === 'DISPUTED'" class="notice danger">
        订单正在售后处理中，请停止继续履约并等待平台处理。
      </view>

      <view class="bottom-spacer"></view>
      <PrimaryActionBar
        v-if="primaryAction"
        :primary-text="primaryAction.label"
        :loading="busy"
        dark
        @primary="runPrimary"
      />
    </template>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#0f0f15; box-sizing:border-box; color:#fff; }
.loading { padding:140rpx 0; color:#777784; text-align:center; font-size:22rpx; }
.hero { padding:36rpx; border-radius:36rpx; background:linear-gradient(145deg,#1a1922,#29263a); color:#fff; }
.hero-top { display:flex; align-items:center; justify-content:space-between; gap:18rpx; }
.order-no { color:#747480; font-size:18rpx; }
.income { margin-top:24rpx; }
.caption { margin-top:7rpx; color:#777784; font-size:20rpx; }
.state-desc { margin:26rpx 0 28rpx; padding-top:24rpx; border-top:1rpx solid rgba(0,0,0,.10); color:#c3c3cc; font-size:22rpx; line-height:1.55; }
.card { margin-top:22rpx; padding:30rpx; border-radius:30rpx; background:#181820; color:#fff; }
.card>view:not(.event) { display:flex; justify-content:space-between; align-items:center; gap:20rpx; padding:18rpx 0; font-size:22rpx; border-bottom:1rpx solid rgba(0,0,0,.08); }
.card>view:last-child { border:0; }
.card text { color:#777784; }
.value { color:#d2d2da !important; font-weight:650; }
.card-title { color:#d7d7df !important; font-size:23rpx !important; font-weight:750; }.card-title-row{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:18rpx!important;border-bottom:0!important;padding-bottom:15rpx!important}.card-action{flex:none;color:#9589df!important;font-size:16rpx!important;font-weight:700}
.event { display:flex; gap:16rpx; min-height:72rpx; }
.track { width:20rpx; display:flex; flex-direction:column; align-items:center; }
.event-dot { width:12rpx; height:12rpx; border-radius:50%; background:#555561; }
.event-dot.latest { background:#9182f5; box-shadow:0 0 0 7rpx rgba(145,130,245,.10); }
.event-line { width:2rpx; flex:1; margin-top:6rpx; background:#30303a; }
.event-copy { flex:1; padding-bottom:20rpx; }
.event-head { display:flex; justify-content:space-between; gap:14rpx; }
.event-head>text:first-child { color:#c8c8d0; font-size:20rpx; }
.time { flex:none; color:#62626e !important; font-size:17rpx !important; }
.actor { display:block; margin-top:5rpx; color:#646470 !important; font-size:17rpx !important; }
.realtime { display:flex;align-items:center;justify-content:space-between;gap:16rpx;margin-top:18rpx;padding:14rpx 16rpx;border-radius:18rpx;background:rgba(211,148,38,.09);color:#b7955a;font-size:17rpx; }
.live-dot { margin-right:8rpx; color:currentColor; }
.refresh { color:#a99df3;font-weight:750; }
.aftercare-hint{display:block;color:#777784;font-size:18rpx;line-height:1.55}.aftercare-card textarea{width:100%;height:125rpx;margin-top:16rpx;padding:17rpx;border-radius:19rpx;background:#23232b;color:#fff;font-size:20rpx}.aftercare-action{display:flex!important;justify-content:flex-end!important;border-bottom:0!important;padding-bottom:0!important}
.notice { margin-top:22rpx; padding:26rpx; border-radius:26rpx; background:#221f31; color:#b3accf; font-size:21rpx; line-height:1.6; }
.notice.success { background:rgba(34,197,94,.10); color:#64cf8e; }
.notice.danger { background:rgba(239,68,68,.10); color:var(--danger-on-inverse); }
.bottom-spacer { height:126rpx; }
</style>
