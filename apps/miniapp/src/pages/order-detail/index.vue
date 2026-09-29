<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { API_ORIGIN, request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Game, Order, ServiceSku } from "../../types/domain"
import {
  isCustomerCancellable,
  orderStatusMeta
} from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const customerUserId = ref("")
const loading = ref(true)
const busy = ref(false)
const socketConnected = ref(false)
const gameName = ref("陪玩服务")
const skuName = ref("服务规格")
const skuMeta = ref("")
const rating = ref(5)
const review = ref("")
const reviewed = ref(false)
let socket: UniApp.SocketTask | null = null
let serviceContextLoaded = false

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status, "CUSTOMER") : null
)

const primaryAction = computed(() => {
  if (!order.value) return null
  if (order.value.status === "WAITING_PAYMENT") return { kind: "pay", label: "去支付" } as const
  if (order.value.status === "FINISH_REQUESTED") return { kind: "confirm", label: "确认完成" } as const
  if (["CANCELLED", "REFUNDED"].includes(order.value.status)) {
    return { kind: "again", label: "再来一单" } as const
  }
  return null
})

const secondaryAction = computed(() => {
  if (!order.value) return null
  if (isCustomerCancellable(order.value.status)) {
    return { kind: "cancel", label: "取消订单" } as const
  }
  return null
})

async function loadServiceContext(current: Order) {
  if (serviceContextLoaded || !current.game_id) return
  try {
    const [games, skus] = await Promise.all([
      request<Game[]>("/games"),
      request<ServiceSku[]>(`/games/${current.game_id}/skus`)
    ])
    gameName.value = games.find(item => item.id === current.game_id)?.name || gameName.value
    const sku = skus.find(item => item.id === current.sku_id)
    if (sku) {
      skuName.value = sku.name
      skuMeta.value = `${sku.duration_minutes} 分钟 · ${sku.service_type}`
    }
    serviceContextLoaded = true
  } catch {
    // Order itself stays usable even if catalog context is temporarily unavailable.
  }
}

async function reload(showToast = false) {
  if (!orderId.value) return
  try {
    const current = await request<Order>(`/orders/${orderId.value}`)
    order.value = current
    await loadServiceContext(current)
    if (showToast) uni.showToast({ title: "状态已刷新", icon: "none" })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "订单加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

function connectRealtime() {
  const task = uni.connectSocket({
    url: API_ORIGIN.replace(/^http/, "ws") + "/ws"
  }) as unknown as UniApp.SocketTask
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
    } catch {
      // Ignore messages that are not order events.
    }
  })
}

onLoad(async query => {
  orderId.value = String(query?.id || "")
  const identities = await getDemoIdentities()
  customerUserId.value = identities.customer.userId
  await reload()
  connectRealtime()
})

onUnload(() => socket?.close({}))

async function cancelOrder() {
  const current = order.value
  if (!current || busy.value || !isCustomerCancellable(current.status)) return
  busy.value = true
  try {
    order.value = await request<Order>(`/orders/${current.id}/cancel`, {
      method: "POST",
      userId: customerUserId.value
    })
    uni.showToast({ title: "订单已取消", icon: "success" })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "取消失败，请刷新后重试",
      icon: "none"
    })
    await reload()
  } finally {
    busy.value = false
  }
}

function orderAgain() {
  const current = order.value
  if (current?.game_id) {
    uni.navigateTo({
      url: `/pages/game/index?id=${current.game_id}&name=${encodeURIComponent(gameName.value)}`
    })
    return
  }
  uni.switchTab({ url: "/pages/home/index" })
}

async function runPrimary() {
  const current = order.value
  const action = primaryAction.value
  if (!current || !action || busy.value) return

  if (action.kind === "again") {
    orderAgain()
    return
  }

  busy.value = true
  try {
    if (action.kind === "pay") {
      order.value = await request<Order>(`/orders/${current.id}/mock-pay`, {
        method: "POST",
        headers: { "Idempotency-Key": `miniapp-${current.id}` }
      })
      uni.showToast({ title: "支付成功", icon: "success" })
    }

    if (action.kind === "confirm") {
      order.value = await request<Order>(`/orders/${current.id}/confirm`, {
        method: "POST",
        userId: customerUserId.value
      })
      uni.showToast({ title: "已确认完成", icon: "success" })
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "操作失败，请刷新后重试",
      icon: "none"
    })
    await reload()
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
      data: {
        rating: rating.value,
        content: review.value.trim()
      }
    })
    reviewed.value = true
    uni.showToast({ title: "评价已提交", icon: "success" })
  } catch (error) {
    const message = error instanceof Error ? error.message : "评价失败"
    if (message.includes("ORDER_ALREADY_REVIEWED")) {
      reviewed.value = true
      uni.showToast({ title: "这笔订单已经评价过了", icon: "none" })
    } else {
      uni.showToast({ title: message, icon: "none" })
    }
  } finally {
    busy.value = false
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
        <text v-if="!socketConnected" class="refresh" @click="reload(true)">刷新</text>
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

      <view class="section-card">
        <view class="card-title">服务信息</view>
        <view class="row">
          <text>游戏</text>
          <text class="value">{{ gameName }}</text>
        </view>
        <view class="row">
          <text>服务规格</text>
          <view class="right">
            <text class="value">{{ skuName }}</text>
            <text v-if="skuMeta" class="sub">{{ skuMeta }}</text>
          </view>
        </view>
        <view class="row">
          <text>数量</text>
          <text class="value">× {{ order.quantity || 1 }}</text>
        </view>
      </view>

      <view class="section-card">
        <view class="card-title">支付信息</view>
        <view class="row">
          <text>订单金额</text>
          <PriceText :cents="order.total_amount" size="md" />
        </view>
        <view v-if="order.unit_price" class="row">
          <text>服务单价</text>
          <PriceText :cents="order.unit_price" size="sm" muted />
        </view>
      </view>

      <view class="security-card">
        <view class="shield">✓</view>
        <view>
          <text class="security-title">平台担保交易</text>
          <text class="security-desc">用户端只展示应付与实付信息；平台分账与陪玩到手价仅在履约侧展示。</text>
        </view>
      </view>

      <view v-if="order.status === 'FINISH_REQUESTED'" class="notice warning">
        陪玩已申请完成。确认前请核对服务是否正常；争议入口将在售后流程接入后展示。
      </view>

      <view v-if="order.status === 'DISPUTED'" class="notice danger">
        当前订单正在售后处理中，请等待平台处理结果。
      </view>

      <view v-if="order.status === 'SETTLED'" class="review-card">
        <view class="card-title">评价本次服务</view>
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
          <textarea
            v-model="review"
            maxlength="1000"
            placeholder="说说这次陪玩体验，可选"
          />
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
.section-card, .review-card { margin-top:20rpx; padding:30rpx; border-radius:30rpx; background:#fff; }
.card-title { padding-bottom:14rpx; color:#17171e; font-size:25rpx; font-weight:780; }
.row { display:flex; align-items:flex-start; justify-content:space-between; gap:22rpx; padding:19rpx 0; border-bottom:1rpx solid #f0f0f4; color:#74747e; font-size:22rpx; }
.row:last-child { border:0; }
.value { color:#282831; font-weight:650; }
.right { text-align:right; }
.sub { display:block; margin-top:5rpx; color:#9a9aa5; font-size:18rpx; }
.security-card { display:flex; gap:18rpx; align-items:center; margin-top:18rpx; padding:24rpx 28rpx; border-radius:28rpx; background:#ecfbf3; }
.shield { width:52rpx; height:52rpx; flex:none; display:flex; align-items:center; justify-content:center; border-radius:18rpx; background:#24b96b; color:#fff; font-weight:850; }
.security-title { display:block; color:#177948; font-size:22rpx; font-weight:750; }
.security-desc { display:block; margin-top:4rpx; color:#55a47b; font-size:18rpx; line-height:1.5; }
.notice { margin-top:18rpx; padding:24rpx 26rpx; border-radius:24rpx; font-size:20rpx; line-height:1.6; }
.notice.warning { background:#fff5e8; color:#a96806; }
.notice.danger { background:#fff0f0; color:#c8474a; }
.stars { display:flex; gap:13rpx; margin-top:10rpx; }
.stars text { color:#d7d7df; font-size:52rpx; }
.stars text.active { color:#f0b72f; }
.rating-copy { display:block; margin-top:6rpx; color:#8d8d98; font-size:19rpx; }
.review-card textarea { width:100%; height:150rpx; margin-top:18rpx; padding:18rpx; border-radius:20rpx; background:#f7f7fb; box-sizing:border-box; font-size:22rpx; }
.review-submit { margin:20rpx 0 0; height:78rpx; line-height:78rpx; border-radius:23rpx; background:#17171f; color:#fff; font-size:23rpx; font-weight:750; }
.reviewed { padding:24rpx 0 8rpx; color:#1c9659; font-size:22rpx; }
.bottom-spacer { height:130rpx; }
</style>
