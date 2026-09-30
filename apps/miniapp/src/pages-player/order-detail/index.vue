<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onShow, onUnload } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { connectOrderRealtime } from "../../api/realtime"
import { getDemoIdentities } from "../../api/demo"
import OrderChat from "../../components/OrderChat.vue"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Order, OrderEvent } from "../../types/domain"
import {
import { showSuccess, showMessage } from "../../ui/feedback"
  orderStatusMeta,
  playerActionErrorMessage
} from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const events = ref<OrderEvent[]>([])
const eventsExpanded = ref(false)
const busy = ref(false)
const loading = ref(true)
const playerUserId = ref("")
const chatRefreshKey = ref(0)
const socketConnected = ref(false)
let socket: UniApp.SocketTask | null = null

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status, "PLAYER") : null
)

const incomeCaption = computed(() =>
  order.value?.status === "SETTLED" ? "本单已结算收入" : "本单预计收入"
)

const visibleEvents = computed(() =>
  eventsExpanded.value || events.value.length <= 4
    ? events.value
    : events.value.slice(-4)
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

const nextAction = computed(() => {
  if (order.value?.status === "ACCEPTED") {
    return { label: "开始服务", endpoint: "start" } as const
  }
  if (order.value?.status === "IN_SERVICE") {
    return { label: "申请完成", endpoint: "finish" } as const
  }
  return null
})

const eventLabels: Record<string, string> = {
  ORDER_CREATED: "订单已创建",
  PAYMENT_SUCCESS: "用户支付成功",
  ORDER_ENTERED_MATCHING: "进入抢单大厅",
  ORDER_CLAIMED: "你已接单",
  ORDER_ASSIGNED: "已分配给你",
  SERVICE_STARTED: "服务已开始",
  FINISH_REQUESTED: "已申请完成",
  USER_CONFIRMED_FINISH: "用户确认完成",
  AUTO_CONFIRMED_FINISH: "超时自动确认",
  ORDER_SETTLED: "订单已结算",
  DISPUTE_OPENED: "订单进入售后",
  REFUND_COMPLETED: "订单已退款"
}

function eventTitle(event: OrderEvent): string {
  if (eventLabels[event.event_type]) return eventLabels[event.event_type]
  if (event.to_status) return orderStatusMeta(event.to_status, "PLAYER").label
  return event.event_type.replaceAll("_", " ")
}

function actorLabel(actor: string): string {
  const labels: Record<string,string> = {
    USER: "用户",
    PLAYER: "你",
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
  return `${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function load() {
  if (!orderId.value || !playerUserId.value) return
  try {
    const [orderResult, eventResult] = await Promise.all([
      request<Order>(`/orders/${orderId.value}`, { userId: playerUserId.value }),
      request<OrderEvent[]>(`/orders/${orderId.value}/events`, { userId: playerUserId.value })
    ])
    order.value = orderResult
    events.value = eventResult
  } catch (error) {
    showMessage(playerActionErrorMessage(error instanceof Error ? error.message : ""))
  } finally {
    loading.value = false
  }
}

async function connectRealtime() {
  if (!orderId.value || !playerUserId.value) return
  const task = await connectOrderRealtime({
    orderId: orderId.value,
    demoUserId: playerUserId.value
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
      if (payload.type === "order.status_changed") void load()
      if (payload.type === "order.message_created") chatRefreshKey.value += 1
    } catch {
      // Ignore non-order realtime messages.
    }
  })
}

async function act() {
  const current = order.value
  const action = nextAction.value
  if (!current || !action || busy.value) return
  busy.value = true
  try {
    order.value = await request<Order>(
      `/player/orders/${current.id}/${action.endpoint}`,
      { method: "POST", userId: playerUserId.value }
    )
    showSuccess(action.endpoint === "start" ? "服务已开始" : "已申请完成")
    await load()
  } catch (error) {
    showMessage(playerActionErrorMessage(error instanceof Error ? error.message : ""))
    await load()
  } finally {
    busy.value = false
  }
}

onLoad(async query => {
  orderId.value = String(query?.id || "")
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  await load()
  await connectRealtime()
})

onUnload(() => socket?.close({}))

onShow(() => {
  if (orderId.value && playerUserId.value && !loading.value) void load()
})
</script>

<template>
  <view class="page">
    <view v-if="loading" class="loading">正在同步服务单…</view>

    <template v-else-if="order && meta">
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
        <text class="live-dot">●</text>
        自动更新暂时中断，页面重新进入后会继续同步
      </view>

      <OrderChat
        v-if="chatVisible"
        :order-id="order.id"
        :user-id="playerUserId"
        :refresh-key="chatRefreshKey"
        :writable="chatWritable"
        dark
      />

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
        v-if="nextAction"
        :primary-text="nextAction.label"
        :loading="busy"
        dark
        @primary="act"
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
.state-desc { margin:26rpx 0 28rpx; padding-top:24rpx; border-top:1rpx solid rgba(255,255,255,.08); color:#c3c3cc; font-size:22rpx; line-height:1.55; }
.card { margin-top:22rpx; padding:30rpx; border-radius:30rpx; background:#181820; color:#fff; }
.card>view:not(.event) { display:flex; justify-content:space-between; align-items:center; gap:20rpx; padding:18rpx 0; font-size:22rpx; border-bottom:1rpx solid rgba(255,255,255,.06); }
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
.realtime { margin-top:18rpx; padding:14rpx 16rpx; border-radius:18rpx; background:rgba(211,148,38,.09); color:#b7955a; font-size:17rpx; }
.live-dot { margin-right:8rpx; color:currentColor; }
.notice { margin-top:22rpx; padding:26rpx; border-radius:26rpx; background:#221f31; color:#b3accf; font-size:21rpx; line-height:1.6; }
.notice.success { background:rgba(34,197,94,.10); color:#64cf8e; }
.notice.danger { background:rgba(239,68,68,.10); color:#dc7779; }
.bottom-spacer { height:126rpx; }
</style>
