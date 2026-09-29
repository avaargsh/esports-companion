<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { connectOrderRealtime } from "../../api/realtime"
import { submitOrderPayment } from "../../api/payment"
import { getDemoIdentities } from "../../api/demo"
import OrderChat from "../../components/OrderChat.vue"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Order, OrderEvent } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const events = ref<OrderEvent[]>([])
const customerUserId = ref("")
const socketConnected = ref(false)
const loading = ref(true)
const busy = ref(false)
const rating = ref(5)
const review = ref("")
const reviewed = ref(false)
const aftercareReason = ref("")
const paymentConfirming = ref(false)
const chatRefreshKey = ref(0)
let socket: UniApp.SocketTask | null = null

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status, "CUSTOMER") : null
)

const chatVisible = computed(() =>
  [
    "ACCEPTED",
    "IN_SERVICE",
    "FINISH_REQUESTED",
    "COMPLETED",
    "SETTLED",
    "DISPUTED",
    "REFUNDING",
    "REFUNDED"
  ].includes(order.value?.status ?? "")
)

const chatWritable = computed(() =>
  ["ACCEPTED", "IN_SERVICE", "FINISH_REQUESTED", "DISPUTED"].includes(
    order.value?.status ?? ""
  )
)

const primaryAction = computed(() => {
  const current = order.value
  if (!current) return null
  if (current.available_actions?.includes("PAY")) {
    return { kind: "pay", label: "去支付" } as const
  }
  if (current.status === "FINISH_REQUESTED") {
    return { kind: "confirm", label: "确认完成" } as const
  }
  if (["CANCELLED", "REFUNDED"].includes(current.status)) {
    return { kind: "again", label: "再来一单" } as const
  }
  return null
})

const secondaryAction = computed(() => {
  const current = order.value
  if (current?.available_actions?.includes("CANCEL")) {
    return { kind: "cancel", label: "取消订单" } as const
  }
  return null
})

const eventLabels: Record<string, string> = {
  ORDER_CREATED: "订单已创建",
  PAYMENT_SUCCESS: "支付成功",
  ORDER_ENTERED_MATCHING: "进入接单队列",
  ORDER_CLAIMED: "陪玩已接单",
  ORDER_ASSIGNED: "陪玩已接单",
  SERVICE_STARTED: "服务已开始",
  FINISH_REQUESTED: "陪玩申请完成",
  USER_CONFIRMED_FINISH: "用户确认完成",
  AUTO_CONFIRMED_FINISH: "超时自动确认",
  ORDER_SETTLED: "订单已结算",
  ORDER_CANCELLED: "订单已取消",
  DISPUTE_OPENED: "已申请平台介入",
  REFUND_REQUESTED: "退款申请处理中",
  REFUND_COMPLETED: "退款已完成"
}

function eventTitle(event: OrderEvent): string {
  if (eventLabels[event.event_type]) return eventLabels[event.event_type]
  if (event.to_status) return orderStatusMeta(event.to_status, "CUSTOMER").label
  return event.event_type.replaceAll("_", " ")
}

function actorLabel(actor: string): string {
  const labels: Record<string, string> = {
    USER: "你",
    PLAYER: "陪玩",
    SYSTEM: "系统",
    PAYMENT: "支付系统",
    PLATFORM: "平台"
  }
  return labels[actor] || "系统"
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function reload() {
  if (!orderId.value) return
  try {
    const [orderResult, eventResult] = await Promise.all([
      request<Order>(`/orders/${orderId.value}`, { userId: customerUserId.value }),
      request<OrderEvent[]>(`/orders/${orderId.value}/events`, { userId: customerUserId.value })
    ])
    order.value = orderResult
    events.value = eventResult
    if (orderResult.status !== "WAITING_PAYMENT") {
      paymentConfirming.value = false
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "订单加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

async function connectRealtime() {
  if (!orderId.value || !customerUserId.value) return
  const task = await connectOrderRealtime({
    orderId: orderId.value,
    demoUserId: customerUserId.value
  })

  socket = task
  task.onOpen(() => {
    socketConnected.value = true
    task.send({
      data: JSON.stringify({
        type: "subscribe",
        channels: [`order:${orderId.value}`]
      })
    })
  })
  task.onClose(() => { socketConnected.value = false })
  task.onError(() => { socketConnected.value = false })
  task.onMessage(message => {
    try {
      const payload = JSON.parse(String(message.data))
      if (payload.type === "order.status_changed") void reload()
      if (payload.type === "order.message_created") chatRefreshKey.value += 1
    } catch {
      // Ignore non-order realtime messages.
    }
  })
}

onLoad(async query => {
  orderId.value = String(query?.id ?? "")
  const identities = await getDemoIdentities()
  customerUserId.value = identities.customer.userId
  await reload()
  await connectRealtime()
})

onUnload(() => socket?.close({}))

async function runPrimary() {
  const current = order.value
  const action = primaryAction.value
  if (!current || !action || busy.value) return

  if (action.kind === "again") {
    if (current.service_player?.id) {
      uni.navigateTo({ url: `/pages/player/index?id=${current.service_player.id}` })
    } else if (current.game_id) {
      uni.navigateTo({ url: `/pages/game/index?id=${current.game_id}` })
    } else {
      uni.switchTab({ url: "/pages/home/index" })
    }
    return
  }

  busy.value = true
  try {
    if (action.kind === "pay") {
      const result = await submitOrderPayment(
        current.id,
        customerUserId.value
      )
      order.value = result.order
      paymentConfirming.value = result.awaitingProviderConfirmation
      uni.showToast({
        title: result.awaitingProviderConfirmation
          ? "支付已提交，等待确认"
          : "支付成功",
        icon: result.awaitingProviderConfirmation ? "none" : "success"
      })
    }

    if (action.kind === "confirm") {
      order.value = await request<Order>(`/orders/${current.id}/confirm`, {
        method: "POST",
        userId: customerUserId.value
      })
      uni.showToast({ title: "已确认完成", icon: "success" })
    }
    await reload()
  } catch (error) {
    const message = error instanceof Error ? error.message : "操作失败，请刷新后重试"
    uni.showToast({
      title: message === "PAYMENT_CANCELLED" ? "已取消支付" : message,
      icon: "none"
    })
    await reload()
  } finally {
    busy.value = false
  }
}

async function cancelOrder() {
  const current = order.value
  if (!current || busy.value) return
  busy.value = true
  try {
    order.value = await request<Order>(`/orders/${current.id}/cancel`, {
      method: "POST",
      userId: customerUserId.value
    })
    uni.showToast({ title: "订单已取消", icon: "success" })
    await reload()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "取消失败",
      icon: "none"
    })
    await reload()
  } finally {
    busy.value = false
  }
}

async function requestAftercare(action: "refund" | "dispute") {
  const current = order.value
  if (!current || busy.value) return
  busy.value = true
  try {
    await request(`/orders/${current.id}/disputes`, {
      method: "POST",
      userId: customerUserId.value,
      headers: { "Idempotency-Key": `miniapp-dispute-${current.id}` },
      data: {
        reason_code: action === "refund" ? "CANCEL_BEFORE_SERVICE" : "SERVICE_ISSUE",
        description: aftercareReason.value.trim()
      }
    })
    aftercareReason.value = ""
    uni.showToast({
      title: action === "refund" ? "退款申请已提交" : "已申请平台介入",
      icon: "none"
    })
    await reload()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "提交失败",
      icon: "none"
    })
  } finally {
    busy.value = false
  }
}

async function submitReview() {
  const current = order.value
  if (!current || reviewed.value || busy.value) return
  busy.value = true
  try {
    await request(`/orders/${current.id}/reviews`, {
      method: "POST",
      userId: customerUserId.value,
      data: { rating: rating.value, content: review.value.trim() }
    })
    reviewed.value = true
    uni.showToast({ title: "评价已提交", icon: "success" })
  } catch (error) {
    const message = error instanceof Error ? error.message : "评价失败"
    if (message.includes("ORDER_ALREADY_REVIEWED")) reviewed.value = true
    uni.showToast({ title: message, icon: "none" })
  } finally {
    busy.value = false
  }
}

function openServicePlayer() {
  if (order.value?.service_player?.id) {
    uni.navigateTo({ url: `/pages/player/index?id=${order.value.service_player.id}` })
  }
}
</script>

<template>
  <view class="page">
    <view v-if="loading" class="loading">正在同步订单状态…</view>

    <template v-else-if="order && meta">
      <view class="realtime" :class="{ offline: !socketConnected }">
        <view class="realtime-copy">
          <text class="dot"></text>
          <text>{{ socketConnected ? "订单状态实时更新中" : "实时连接已断开，可手动刷新" }}</text>
        </view>
        <text v-if="!socketConnected" class="refresh" @click="reload">刷新</text>
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
        <view class="section-title">支付信息</view>
        <view class="row">
          <text>订单金额</text>
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
        <view class="section-title">订单进展</view>
        <view class="timeline">
          <view v-for="(event, index) in events" :key="event.id" class="event">
            <view class="track">
              <view class="event-dot" :class="{ latest: index === events.length - 1 }"></view>
              <view v-if="index < events.length - 1" class="event-line"></view>
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

      <view v-if="order.status === 'WAITING_PAYMENT' && paymentConfirming" class="notice payment-confirming">
        <text class="notice-title">微信支付已提交</text>
        <text>正在等待服务端收到微信支付成功通知；订单状态以服务端验签结果为准。</text>
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
        <view class="section-title">售后与争议</view>
        <view class="aftercare-hint">
          退款和服务争议都会进入平台审核；提交后订单资金保持冻结。
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
.page { min-height:100vh; padding:24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)); }
.loading { padding:140rpx 0; color:#92929d; text-align:center; font-size:22rpx; }
.realtime { display:flex; align-items:center; justify-content:space-between; gap:16rpx; margin-bottom:14rpx; padding:14rpx 18rpx; border-radius:18rpx; background:#eafbf2; color:#278156; font-size:19rpx; }
.realtime.offline { background:#f3f3f6; color:#7b7b86; }
.realtime-copy { display:flex; align-items:center; gap:9rpx; }
.dot { width:12rpx; height:12rpx; border-radius:50%; background:currentColor; }
.refresh { color:#6c5ce7; font-weight:700; }
.status-card { padding:34rpx; border-radius:36rpx; background:linear-gradient(145deg,#17171f,#282636 72%,#3b345e); color:#fff; box-shadow:0 18rpx 50rpx rgba(20,19,34,.18); }
.status-top { display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.no { color:#9694a6; font-size:18rpx; }
.status { margin-top:28rpx; font-size:40rpx; font-weight:850; }
.status-desc { display:block; margin:9rpx 0 34rpx; color:#aaa8b8; font-size:21rpx; line-height:1.55; }
.section-card { margin-top:20rpx; padding:30rpx; border-radius:30rpx; background:#fff; }
.section-title { padding-bottom:14rpx; color:#17171e; font-size:25rpx; font-weight:780; }
.provider-card { cursor:pointer; }
.provider-row { display:flex; align-items:center; gap:18rpx; padding-top:6rpx; }
.provider-avatar { width:84rpx; height:84rpx; flex:none; border-radius:25rpx; }
.provider-avatar.fallback { display:flex; align-items:center; justify-content:center; background:#17171f; color:#fff; font-size:30rpx; font-weight:800; }
.provider-copy { flex:1; min-width:0; }
.provider-name { font-size:27rpx; font-weight:750; }
.provider-meta { margin-top:7rpx; color:#92929d; font-size:20rpx; }
.chevron { color:#b2b2bc; font-size:34rpx; }
.row { display:flex; align-items:center; justify-content:space-between; gap:22rpx; padding:19rpx 0; border-bottom:1rpx solid #f0f0f4; color:#74747e; font-size:22rpx; }
.row:last-child { border:0; }
.value { color:#282831; font-weight:650; }
.timeline { padding-top:4rpx; }
.event { display:flex; gap:18rpx; min-height:78rpx; }
.track { width:22rpx; flex:none; display:flex; flex-direction:column; align-items:center; }
.event-dot { width:14rpx; height:14rpx; border-radius:50%; background:#c8c8d1; }
.event-dot.latest { background:#6c5ce7; box-shadow:0 0 0 8rpx #f0edff; }
.event-line { width:2rpx; flex:1; margin-top:6rpx; background:#e5e5eb; }
.event-copy { flex:1; min-width:0; padding-bottom:24rpx; }
.event-head { display:flex; justify-content:space-between; gap:16rpx; }
.event-title { color:#2b2b33; font-size:22rpx; font-weight:700; }
.event-time { flex:none; color:#a2a2ac; font-size:18rpx; }
.event-actor { display:block; margin-top:5rpx; color:#9a9aa4; font-size:18rpx; }
.notice { margin-top:18rpx; padding:24rpx 26rpx; border-radius:24rpx; background:#f1efff; color:#6c5ce7; font-size:20rpx; line-height:1.6; }
.notice.designated { background:#fff5e8; color:#a96806; }
.notice.payment-confirming { background:#eef7ff; color:#24689b; }
.notice-title { display:block; margin-bottom:5rpx; font-weight:750; }
.aftercare-hint { color:#92929d; font-size:20rpx; line-height:1.55; }
.aftercare-card textarea, .review-card textarea { width:100%; height:140rpx; margin-top:18rpx; padding:18rpx; border-radius:20rpx; background:#f7f7fb; box-sizing:border-box; font-size:22rpx; }
.aftercare-actions { display:flex; gap:14rpx; margin-top:16rpx; }
.aftercare-actions button { flex:1; margin:0; height:76rpx; line-height:76rpx; border-radius:22rpx; font-size:21rpx; }
.ghost { background:#f3f3f6; color:#656570; }
.ghost.danger { background:#fff0f0; color:#c9494d; }
.stars { display:flex; gap:13rpx; margin-top:10rpx; }
.stars text { color:#d7d7df; font-size:52rpx; }
.stars text.active { color:#f0b72f; }
.rating-copy { display:block; margin-top:6rpx; color:#8d8d98; font-size:19rpx; }
.review-submit { margin:20rpx 0 0; height:78rpx; line-height:78rpx; border-radius:23rpx; background:#17171f; color:#fff; font-size:23rpx; font-weight:750; }
.reviewed { padding:24rpx 0 8rpx; color:#1c9659; font-size:22rpx; }
.bottom-spacer { height:130rpx; }
</style>
