<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { API_ORIGIN, request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order } from "../../types/domain"

const orderId = ref("")
const order = ref<Order | null>(null)
const customerUserId = ref("")
const busy = ref(false)
let socket: UniApp.SocketTask | null = null

const labels: Record<string, { title: string; desc: string }> = {
  WAITING_PAYMENT: { title: "等待支付", desc: "支付后系统会把订单推送给合适的陪玩师" },
  PAID: { title: "支付成功", desc: "订单已进入匹配队列" },
  MATCHING: { title: "正在匹配陪玩师", desc: "订单已进入实时抢单池" },
  ACCEPTED: { title: "陪玩师已接单", desc: "陪玩师会尽快开始服务" },
  IN_SERVICE: { title: "服务进行中", desc: "祝你们游戏愉快" },
  FINISH_REQUESTED: { title: "陪玩师申请结束", desc: "确认服务完成后平台会进行结算" },
  COMPLETED: { title: "服务已完成", desc: "本次服务已经完成" },
  SETTLED: { title: "订单已结算", desc: "可以为本次服务留下评价" },
  CANCELLED: { title: "订单已取消", desc: "本次订单已关闭" },
  REFUNDING: { title: "退款处理中", desc: "退款正在处理中" },
  REFUNDED: { title: "已退款", desc: "订单金额已原路退回" },
  DISPUTED: { title: "售后处理中", desc: "平台正在处理本次争议" }
}

const state = computed(() =>
  order.value ? (labels[order.value.status] || { title: order.value.status, desc: "" }) : null
)

const progress = computed(() => {
  if (!order.value) return 0
  const map: Record<string, number> = {
    WAITING_PAYMENT: 1,
    PAID: 2,
    MATCHING: 2,
    ACCEPTED: 3,
    IN_SERVICE: 4,
    FINISH_REQUESTED: 4,
    COMPLETED: 5,
    SETTLED: 5
  }
  return map[order.value.status] || 1
})

const action = computed(() => {
  if (!order.value) return null
  if (order.value.status === "WAITING_PAYMENT") return ["支付并开始匹配", "pay"] as const
  if (order.value.status === "FINISH_REQUESTED") return ["确认服务完成", "confirm"] as const
  if (order.value.status === "SETTLED") return ["五星好评", "review"] as const
  return null
})

async function reload() {
  if (!orderId.value) return
  order.value = await request<Order>(`/orders/${orderId.value}`)
}

function connectRealtime() {
  const task = uni.connectSocket({
    url: API_ORIGIN.replace(/^http/, "ws") + "/ws"
  }) as unknown as UniApp.SocketTask
  socket = task

  task.onOpen(() => {
    task.send({
      data: JSON.stringify({
        type: "subscribe",
        channels: [`order:${orderId.value}`]
      })
    })
  })
  task.onMessage(message => {
    try {
      const payload = JSON.parse(String(message.data))
      if (payload.type === "order.status_changed") void reload()
    } catch {
      // Ignore development messages that are not JSON.
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

async function run() {
  const current = order.value
  const currentAction = action.value
  if (!current || !currentAction || busy.value) return

  busy.value = true
  try {
    const kind = currentAction[1]
    if (kind === "pay") {
      order.value = await request<Order>(`/orders/${current.id}/mock-pay`, {
        method: "POST",
        headers: { "Idempotency-Key": `miniapp-${current.id}` }
      })
      uni.showToast({ title: "支付成功", icon: "success" })
    }

    if (kind === "confirm") {
      order.value = await request<Order>(`/orders/${current.id}/confirm`, {
        method: "POST",
        userId: customerUserId.value
      })
      uni.showToast({ title: "已确认完成", icon: "success" })
    }

    if (kind === "review") {
      await request(`/orders/${current.id}/reviews`, {
        method: "POST",
        userId: customerUserId.value,
        data: { rating: 5, content: "体验很好" }
      })
      uni.showToast({ title: "评价成功", icon: "success" })
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "操作失败",
      icon: "none"
    })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <view class="page" v-if="order && state">
    <view class="status-card">
      <view class="status-top"><text class="badge">订单进度</text><text class="no">{{ order.order_no }}</text></view>
      <view class="status">{{ state.title }}</view>
      <text class="status-desc">{{ state.desc }}</text>
      <view class="progress">
        <view v-for="i in 5" :key="i" class="node" :class="{active:i<=progress}"></view>
      </view>
      <view class="progress-labels"><text>下单</text><text>匹配</text><text>接单</text><text>服务</text><text>完成</text></view>
    </view>

    <view class="money-card">
      <view class="card-title">费用明细</view>
      <view class="row"><text>订单金额</text><text class="strong">¥{{ (order.total_amount/100).toFixed(2) }}</text></view>
      <view class="row"><text>陪玩服务费</text><text>¥{{ (order.player_amount/100).toFixed(2) }}</text></view>
      <view class="row"><text>平台保障服务</text><text>¥{{ (order.platform_fee/100).toFixed(2) }}</text></view>
    </view>

    <view class="security-card">
      <view class="shield">✓</view>
      <view><text class="security-title">平台担保交易</text><text class="security-desc">确认完成后再结算，异常订单可进入售后流程。</text></view>
    </view>

    <button v-if="action" class="primary" @click="run">{{ busy ? "处理中…" : action[0] }}</button>
  </view>
</template>

<style scoped>
.page { padding:28rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)); }
.status-card { padding:34rpx; border-radius:36rpx; background:linear-gradient(145deg,#17171f,#282636 72%,#3b345e); color:#fff; box-shadow:0 18rpx 50rpx rgba(20,19,34,.18); }
.status-top { display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.badge { padding:8rpx 14rpx; border-radius:999rpx; background:rgba(255,255,255,.10); color:#d8d6e5; font-size:18rpx; }
.no { color:#9694a6; font-size:18rpx; }
.status { margin-top:28rpx; font-size:40rpx; font-weight:850; }
.status-desc { display:block; margin-top:9rpx; color:#aaa8b8; font-size:21rpx; }
.progress { display:flex; gap:8rpx; margin-top:34rpx; }
.node { flex:1; height:8rpx; border-radius:999rpx; background:rgba(255,255,255,.10); }
.node.active { background:#8b7cf6; }
.progress-labels { display:flex; justify-content:space-between; margin-top:10rpx; color:#777585; font-size:16rpx; }
.money-card { margin-top:20rpx; padding:30rpx; border-radius:30rpx; background:#fff; }
.card-title { padding-bottom:14rpx; font-size:25rpx; font-weight:780; }
.row { display:flex; justify-content:space-between; padding:19rpx 0; border-bottom:1rpx solid #f0f0f4; color:#74747e; font-size:22rpx; }
.row:last-child { border:0; }
.strong { color:#15151b; font-size:28rpx; font-weight:850; }
.security-card { display:flex; gap:18rpx; align-items:center; margin-top:18rpx; padding:24rpx 28rpx; border-radius:28rpx; background:#ecfbf3; }
.shield { width:52rpx; height:52rpx; flex:none; display:flex; align-items:center; justify-content:center; border-radius:18rpx; background:#24b96b; color:#fff; font-weight:850; }
.security-title { display:block; color:#177948; font-size:22rpx; font-weight:750; }
.security-desc { display:block; margin-top:4rpx; color:#55a47b; font-size:18rpx; }
.primary { margin-top:26rpx; height:86rpx; line-height:86rpx; border-radius:26rpx; background:#6c5ce7; color:#fff; font-size:26rpx; font-weight:750; }
</style>
