<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { connectOrderRealtime } from "../../api/realtime"
import { getDemoIdentities } from "../../api/demo"
import OrderChat from "../../components/OrderChat.vue"
import type { Order } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const busy = ref(false)
const playerUserId = ref("")
const chatRefreshKey = ref(0)
const socketConnected = ref(false)
let socket: UniApp.SocketTask | null = null

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status) : null
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
    return { label: "开始服务", endpoint: "start" }
  }
  if (order.value?.status === "IN_SERVICE") {
    return { label: "申请结束服务", endpoint: "finish" }
  }
  return null
})

async function load() {
  if (!orderId.value || !playerUserId.value) return
  order.value = await request<Order>(
    `/orders/${orderId.value}`,
    { userId: playerUserId.value }
  )
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
      // Ignore non-JSON development messages.
    }
  })
}

async function act() {
  if (!order.value || !nextAction.value || busy.value) return
  busy.value = true
  try {
    if (!playerUserId.value) throw new Error("DEMO_PLAYER_NOT_FOUND")

    order.value = await request<Order>(
      `/player/orders/${order.value.id}/${nextAction.value.endpoint}`,
      { method: "POST", userId: playerUserId.value }
    )
    uni.showToast({
      title: nextAction.value.endpoint === "start" ? "服务已开始" : "已申请结束",
      icon: "success"
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "操作失败",
      icon: "none"
    })
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
</script>

<template>
  <view v-if="order && meta" class="page">
    <view class="hero">
      <view class="status">{{ meta.label }}</view>
      <view class="income">¥{{ (order.player_amount / 100).toFixed(2) }}</view>
      <view class="caption">本单陪玩收入</view>
      <view class="state-desc">{{ meta.description }}</view>
    </view>

    <view class="card">
      <view><text>订单号</text><b>{{ order.order_no }}</b></view>
      <view><text>用户实付</text><b>¥{{ (order.total_amount / 100).toFixed(2) }}</b></view>
      <view><text>平台服务费</text><b>¥{{ (order.platform_fee / 100).toFixed(2) }}</b></view>
    </view>

    <view class="realtime">
      <text class="live-dot" :class="{ online: socketConnected }">●</text>
      {{ socketConnected ? "订单实时连接已建立" : "订单实时连接中" }}
    </view>

    <OrderChat
      v-if="chatVisible"
      :order-id="order.id"
      :user-id="playerUserId"
      :refresh-key="chatRefreshKey"
      :writable="chatWritable"
      dark
    />

    <button
      v-if="nextAction"
      class="primary"
      :loading="busy"
      @click="act"
    >
      {{ nextAction.label }}
    </button>

    <view v-else class="notice">
      {{ order.status === "FINISH_REQUESTED"
        ? "已申请结束，等待用户确认完成并结算。"
        : "当前没有需要执行的动作。" }}
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 28rpx; background: #0f0f15; box-sizing: border-box; }
.hero { padding: 40rpx; border-radius: 36rpx; background: linear-gradient(145deg,#1a1922,#29263a); color: #fff; }
.status { color: #aaaab4; font-size: 23rpx; }
.income { margin-top: 18rpx; font-size: 58rpx; font-weight: 800; }
.caption { margin-top: 7rpx; color: #777784; font-size: 20rpx; }
.state-desc { margin-top: 28rpx; padding-top: 24rpx; border-top: 1rpx solid rgba(255,255,255,.08); color: #c3c3cc; font-size: 22rpx; }
.card { margin-top: 22rpx; padding: 30rpx; border-radius: 30rpx; background: #181820; color: #fff; }
.card view { display: flex; justify-content: space-between; padding: 18rpx 0; font-size: 22rpx; border-bottom: 1rpx solid rgba(255,255,255,.06); }
.card view:last-child { border: 0; }
.card text { color: #777784; }
.card b { font-weight: 600; }
.realtime { margin-top: 22rpx; color: #777784; font-size: 19rpx; }
.live-dot { margin-right: 8rpx; color: #64646f; }
.live-dot.online { color: #47d182; }
.primary { margin-top: 26rpx; height: 88rpx; line-height: 88rpx; border-radius: 28rpx; background: #6c5ce7; color: #fff; font-size: 28rpx; font-weight: 700; }
.notice { margin-top: 26rpx; padding: 26rpx; border-radius: 26rpx; background: #181820; color: #aaaab4; font-size: 23rpx; line-height: 1.6; }
</style>
