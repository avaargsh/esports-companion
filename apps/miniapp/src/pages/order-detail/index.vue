<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { startOrderPayment } from "../../api/payment"
import { connectOrderRealtime } from "../../api/realtime"
import { getDemoIdentities } from "../../api/demo"
import OrderChat from "../../components/OrderChat.vue"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Order, OrderEvent } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"
import { confirmAction, showSuccess, showMessage } from "../../ui/feedback"

const orderId = ref("")
const order = ref<Order | null>(null)
const events = ref<OrderEvent[]>([])
const eventsExpanded = ref(false)
const customerUserId = ref("")
const socketConnected = ref(false)
const loading = ref(true)
const busy = ref(false)
const rating = ref(5)
const review = ref("")
const reviewed = ref(false)
const aftercareReason = ref("")
const chatRefreshKey = ref(0)
let socket: UniApp.SocketTask | null = null

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status, "CUSTOMER") : null
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
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "订单加载失败")
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

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function waitForPaymentConfirmation() {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    if (attempt > 0) await sleep(750)
    await reload()
    if (order.value && order.value.status !== "WAITING_PAYMENT") {
      return true
    }
  }
  return false
}

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

  if (action.kind === "confirm") {
    const confirmed = await confirmAction({
      title: "确认服务已完成？",
      content: "确认后订单将进入结算流程；如果服务存在问题，请先申请退款或平台介入。",
      confirmText: "确认完成"
    })
    if (!confirmed) return
  }

  busy.value = true
  try {
    if (action.kind === "pay") {
      const result = await startOrderPayment(current.id, customerUserId.value)
      if (result.mode === "mock") {
        order.value = result.order
        showSuccess("支付成功")
      } else {
        const confirmed = result.alreadyConfirmed || await waitForPaymentConfirmation()
        if (confirmed) showSuccess("支付已确认")
        else showMessage("支付结果确认中，请稍后刷新", 2600)
      }
    }

    if (action.kind === "confirm") {
      order.value = await request<Order>(`/orders/${current.id}/confirm`, {
        method: "POST",
        userId: customerUserId.value
      })
      showSuccess("已确认完成")
    }
    await reload()
  } catch (error) {
    const message = error instanceof Error ? error.message : "操作失败，请刷新后重试"
    showMessage(message === "PAYMENT_CANCELLED" ? "已取消支付" : message)
    await reload()
  } finally {
    busy.value = false
  }
}

async function cancelOrder() {
  const current = order.value
  if (!current || busy.value) return

  const confirmed = await confirmAction({
    title: "取消订单？",
    content: "取消后订单将不再继续履约，相关资金会按当前订单规则处理。",
    confirmText: "确认取消",
    tone: "danger"
  })
  if (!confirmed) return

  busy.value = true
  try {
    order.value = await request<Order>(`/orders/${current.id}/cancel`, {
      method: "POST",
      userId: customerUserId.value
    })
    showSuccess("订单已取消")
    await reload()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "取消失败")
    await reload()
  } finally {
    busy.value = false
  }
}

async function requestAftercare(action: "refund" | "dispute") {
  const current = order.value
  if (!current || busy.value) return

  const confirmed = await confirmAction({
    title: action === "refund" ? "提交退款申请？" : "申请平台介入？",
    content: action === "refund"
      ? "提交后订单会进入平台处理流程，资金结算可能暂停。"
      : "平台介入后会根据订单记录和双方信息处理争议，资金结算可能暂停。",
    confirmText: action === "refund" ? "提交退款" : "申请介入",
    tone: action === "refund" ? "danger" : "brand"
  })
  if (!confirmed) return

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
    showSuccess(action === "refund" ? "退款申请已提交" : "已申请平台介入")
    await reload()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "提交失败")
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
    showSuccess("评价已提交")
  } catch (error) {
    const message = error instanceof Error ? error.message : "评价失败"
    if (message.includes("ORDER_ALREADY_REVIEWED")) reviewed.value = true
    showMessage(message)
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
      <view v-if="!socketConnected" class="realtime offline">
        <view class="realtime-copy">
          <text class="dot"></text>
          <text>自动更新暂时中断，可手动刷新</text>
        </view>
        <text class="refresh" @click="reload">刷新</text>
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