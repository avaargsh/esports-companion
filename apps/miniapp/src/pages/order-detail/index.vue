<script setup lang="ts">
import { onLoad, onShow, onUnload } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import OrderChat from "../../components/OrderChat.vue"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import SampleJourney from "../../components/SampleJourney.vue"
import StatusTag from "../../components/StatusTag.vue"
import { useCustomerOrderDetail } from "../../features/order-detail/useCustomerOrderDetail"

const {
  order,
  events,
  eventsExpanded,
  customerUserId,
  socketConnected,
  busy,
  rating,
  review,
  reviewed,
  aftercareReason,
  chatRefreshKey,
  demoMode,
  loadStatus,
  loadMessage,
  meta,
  demoJourney,
  visibleEvents,
  chatVisible,
  chatWritable,
  primaryAction,
  secondaryAction,
  init,
  refresh,
  retry,
  dispose,
  runPrimary,
  cancelOrder,
  requestAftercare,
  submitReview,
  openServicePlayer,
  eventTitle,
  actorLabel,
  formatTime
} = useCustomerOrderDetail()

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
      正在同步订单状态…
    </view>

    <EmptyState
      v-else-if="loadStatus === 'error'"
      title="订单暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      @action="retry"
    />

    <template v-else-if="order && meta">
      <SampleJourney
        v-if="demoMode && demoJourney"
        :step="demoJourney.step"
        :title="demoJourney.title"
        :description="demoJourney.description"
      />

      <view v-if="!socketConnected" class="realtime offline">
        <view class="realtime-copy">
          <text class="dot"></text>
          <text>自动更新暂时中断，可手动刷新</text>
        </view>
        <text class="refresh" @click="refresh">刷新</text>
      </view>

      <view class="status-card">
        <view class="status-top">
          <StatusTag :status="order.status" role="CUSTOMER" />
          <text class="no">{{ order.order_no }}</text>
        </view>
        <view class="status">{{ meta.label }}</view>
        <text class="status-desc">{{ meta.description }}</text>
        <OrderProgress :status="order.status" role="CUSTOMER" dark />
      </view>

      <view v-if="order.service_player" class="section-card provider-card" @click="openServicePlayer">
        <view class="section-title">
          {{ order.service_player.binding === "ASSIGNED" ? "服务大神" : "已指定大神" }}
        </view>
        <view class="provider-row">
          <image
            v-if="order.service_player.avatar_url"
            class="provider-avatar"
            :src="order.service_player.avatar_url"
            mode="aspectFill"
          />
          <view v-else class="provider-avatar fallback">
            {{ order.service_player.display_name.slice(0, 1) }}
          </view>
          <view class="provider-copy">
            <view class="provider-name">{{ order.service_player.display_name }}</view>
            <view class="provider-meta">
              {{ order.service_player.rating > 0 ? order.service_player.rating.toFixed(1) + " ★" : "新大神" }}
              · {{ order.service_player.service_status === "AVAILABLE" ? "在线" : "服务中" }}
            </view>
          </view>
          <text class="chevron">›</text>
        </view>
      </view>

      <view class="section-card">
        <view class="section-title">费用明细</view>
        <view class="row">
          <text>合计</text>
          <PriceText :cents="order.total_amount" size="md" />
        </view>
        <view v-if="order.unit_price" class="row">
          <text>服务单价</text>
          <PriceText :cents="order.unit_price" size="sm" muted />
        </view>
        <view class="row">
          <text>服务数量</text>
          <text class="value">× {{ order.quantity || 1 }}</text>
        </view>
      </view>

      <view v-if="events.length" class="section-card">
        <view class="section-title-row">
          <view class="section-title">订单进展</view>
          <text v-if="events.length > 4" class="section-action" @click="eventsExpanded = !eventsExpanded">
            {{ eventsExpanded ? "收起" : "查看全部 " + events.length + " 条" }}
          </text>
        </view>
        <view class="timeline">
          <view v-for="(event, index) in visibleEvents" :key="event.id" class="event">
            <view class="track">
              <view class="event-dot" :class="{ latest: index === visibleEvents.length - 1 }"></view>
              <view v-if="index < visibleEvents.length - 1" class="event-line"></view>
            </view>
            <view class="event-copy">
              <view class="event-head">
                <text class="event-title">{{ eventTitle(event) }}</text>
                <text class="event-time">{{ formatTime(event.created_at) }}</text>
              </view>
              <text class="event-actor">{{ actorLabel(event.actor_type) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="order.status === 'WAITING_PAYMENT' && order.designated_player_id" class="notice designated">
        <text class="notice-title">已锁定指定大神</text>
        <text>支付成功后将直接绑定该大神，不进入公开抢单池。</text>
      </view>

      <view v-if="order.status === 'MATCHING'" class="notice">
        <text class="notice-title">等待接单</text>
        <text>订单已进入抢单大厅，接单后会自动刷新，无需重复下单。</text>
      </view>

      <OrderChat
        v-if="chatVisible"
        :order-id="order.id"
        :user-id="customerUserId"
        :refresh-key="chatRefreshKey"
        :writable="chatWritable"
      />

      <view
        v-if="order.available_actions?.includes('REQUEST_REFUND') || order.available_actions?.includes('OPEN_DISPUTE')"
        class="section-card aftercare-card"
      >
        <view class="section-title">遇到问题？</view>
        <view class="aftercare-hint">
          退款或服务问题会进入平台处理，处理期间资金不会继续结算。
        </view>
        <textarea
          v-model="aftercareReason"
          maxlength="500"
          placeholder="简单说明原因，便于平台处理"
        />
        <view class="aftercare-actions">
          <button
            v-if="order.available_actions?.includes('REQUEST_REFUND')"
            class="ghost danger"
            :disabled="busy"
            @click="requestAftercare('refund')"
          >申请退款</button>
          <button
            v-if="order.available_actions?.includes('OPEN_DISPUTE')"
            class="ghost"
            :disabled="busy"
            @click="requestAftercare('dispute')"
          >申请平台介入</button>
        </view>
      </view>

      <view v-if="order.status === 'SETTLED'" class="section-card review-card">
        <view class="section-title">评价本次服务</view>
        <template v-if="!reviewed">
          <view class="stars">
            <text
              v-for="value in 5"
              :key="value"
              :class="{ active: value <= rating }"
              @click="rating = value"
            >★</text>
          </view>
          <text class="rating-copy">{{ rating }} 星</text>
          <textarea v-model="review" maxlength="1000" placeholder="说说这次陪玩体验，可选" />
          <button class="review-submit" :loading="busy" @click="submitReview">提交评价</button>
        </template>
        <view v-else class="reviewed">评价已提交，感谢反馈。</view>
      </view>

      <view class="bottom-spacer"></view>

      <PrimaryActionBar
        :primary-text="primaryAction?.label || ''"
        :secondary-text="secondaryAction?.label || ''"
        :loading="busy"
        @primary="runPrimary"
        @secondary="cancelOrder"
      />
    </template>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:20rpx 28rpx calc(48rpx + env(safe-area-inset-bottom))}
.loading{padding:150rpx 0;color:var(--muted);text-align:center;font-size:20rpx}
.realtime{display:flex;align-items:center;justify-content:space-between;gap:14rpx;margin-bottom:12rpx;padding:12rpx 16rpx;border-radius:17rpx;background:var(--success-soft);color:var(--success);font-size:17rpx}
.realtime.offline{background:#ececf1;color:#75757f}.realtime-copy{display:flex;align-items:center;gap:8rpx}.dot{width:10rpx;height:10rpx;border-radius:50%;background:currentColor}.refresh{color:var(--brand);font-weight:750}
.status-card{position:relative;overflow:hidden;padding:32rpx;border-radius:38rpx;background:linear-gradient(145deg,#191821,#28243a 65%,#4b4090 135%);color:#fff;box-shadow:0 24rpx 64rpx rgba(28,24,48,.18)}
.status-card::after{content:"";position:absolute;width:260rpx;height:260rpx;right:-110rpx;top:-130rpx;border-radius:50%;background:rgba(120,101,239,.2)}
.status-top{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:20rpx}.no{color:#7f7c8c;font-size:15rpx}
.status{position:relative;z-index:1;margin-top:27rpx;font-size:39rpx;font-weight:850;letter-spacing:-1rpx}.status-desc{position:relative;z-index:1;display:block;margin:8rpx 0 31rpx;color:#aaa7b7;font-size:19rpx;line-height:1.55}
.section-card{margin-top:16rpx;padding:27rpx;border:1rpx solid rgba(20,20,30,.035);border-radius:29rpx;background:#fff;box-shadow:var(--shadow-card)}
.section-title{padding-bottom:13rpx;color:var(--ink);font-size:24rpx;font-weight:790}.section-title-row{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx}.section-action{padding:2rpx 0 13rpx;color:var(--brand);font-size:17rpx;font-weight:700}.provider-card{cursor:pointer}.provider-row{display:flex;align-items:center;gap:17rpx;padding-top:5rpx}.provider-avatar{width:82rpx;height:82rpx;flex:none;border-radius:24rpx}.provider-avatar.fallback{display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,#23212e,var(--brand));color:#fff;font-size:28rpx;font-weight:850}.provider-copy{flex:1;min-width:0}.provider-name{font-size:25rpx;font-weight:780}.provider-meta{margin-top:6rpx;color:var(--muted);font-size:18rpx}.chevron{color:#bbb9c3;font-size:31rpx}
.row{display:flex;align-items:center;justify-content:space-between;gap:20rpx;padding:17rpx 0;border-bottom:1rpx solid #f0eff4;color:#75757f;font-size:20rpx}.row:last-child{border:0}.value{color:var(--ink-2);font-weight:700}
.timeline{padding-top:3rpx}.event{display:flex;gap:16rpx;min-height:72rpx}.track{width:20rpx;flex:none;display:flex;flex-direction:column;align-items:center}.event-dot{width:12rpx;height:12rpx;border-radius:50%;background:#c7c6cf}.event-dot.latest{background:var(--brand);box-shadow:0 0 0 7rpx var(--brand-soft)}.event-line{width:2rpx;flex:1;margin-top:5rpx;background:#e7e6ec}.event-copy{flex:1;min-width:0;padding-bottom:21rpx}.event-head{display:flex;justify-content:space-between;gap:14rpx}.event-title{color:var(--ink);font-size:20rpx;font-weight:730}.event-time{flex:none;color:#aaa9b2;font-size:16rpx}.event-actor{display:block;margin-top:4rpx;color:#9998a2;font-size:16rpx}
.notice{margin-top:15rpx;padding:21rpx 23rpx;border-radius:22rpx;background:var(--brand-soft);color:#6254b7;font-size:18rpx;line-height:1.55}.notice.designated{background:var(--warning-soft);color:#976315}.notice-title{display:block;margin-bottom:4rpx;font-weight:780}
.aftercare-hint{color:var(--muted);font-size:18rpx;line-height:1.55}.aftercare-card textarea,.review-card textarea{width:100%;height:125rpx;margin-top:16rpx;padding:17rpx;border-radius:19rpx;background:#f7f7fa;font-size:20rpx}.aftercare-actions{display:flex;gap:12rpx;margin-top:14rpx}.aftercare-actions button{flex:1;height:72rpx;margin:0;line-height:72rpx;border-radius:21rpx;font-size:19rpx}.ghost{background:#efeff3;color:#60606b}.ghost.danger{background:var(--danger-soft);color:var(--danger)}
.stars{display:flex;gap:11rpx;margin-top:7rpx}.stars text{color:#d9d8df;font-size:48rpx}.stars text.active{color:#e9aa2d}.rating-copy{display:block;margin-top:5rpx;color:var(--muted);font-size:17rpx}.review-submit{margin:18rpx 0 0;height:74rpx;line-height:74rpx;border-radius:22rpx;background:var(--ink);color:#fff;font-size:21rpx;font-weight:760}.reviewed{padding:21rpx 0 7rpx;color:var(--success);font-size:20rpx}.bottom-spacer{height:128rpx}
</style>