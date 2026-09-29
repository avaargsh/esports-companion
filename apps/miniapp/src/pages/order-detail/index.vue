<script setup lang="ts">
import { onLoad, onUnload } from "@dcloudio/uni-app"
import { ref } from "vue"
import { API_ORIGIN, request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Order = {
  id: string
  order_no: string
  status: string
  total_amount: number
  player_amount: number
  platform_fee: number
  version: number
}

const orderId = ref("")
const order = ref<Order | null>(null)
let socket: UniApp.SocketTask | null = null

async function reload() {
  if (!orderId.value) return
  order.value = await request<Order>(`/orders/${orderId.value}`)
}

function connectRealtime() {
  socket = uni.connectSocket({
    url: API_ORIGIN.replace(/^http/, "ws") + "/ws"
  })
  socket.onOpen(() => {
    socket?.send({
      data: JSON.stringify({
        type: "subscribe",
        channels: [`order:${orderId.value}`]
      })
    })
  })
  socket.onMessage((message) => {
    try {
      const payload = JSON.parse(String(message.data))
      if (payload.type === "order.status_changed") reload()
    } catch {
      // Ignore non-JSON development messages.
    }
  })
}

onLoad(async (query) => {
  orderId.value = String(query?.id ?? "")
  await reload()
  connectRealtime()
})

onUnload(() => socket?.close({}))

async function mockPay() {
  if (!order.value) return
  try {
    order.value = await request<Order>(`/orders/${order.value.id}/mock-pay`, {
      method: "POST",
      headers: { "Idempotency-Key": `miniapp-${order.value.id}` }
    })
    uni.showToast({ title: "支付成功", icon: "success" })
  } catch (error) {
    uni.showToast({ title: error instanceof Error ? error.message : "支付失败", icon: "none" })
  }
}

async function confirmFinish() {
  if (!order.value) return
  const identities = await getDemoIdentities()
  order.value = await request<Order>(`/orders/${order.value.id}/confirm`, {
    method: "POST",
    userId: identities.customer.userId
  })
  uni.showToast({ title: "已完成结算", icon: "success" })
}
</script>

<template>
  <view v-if="order" class="page">
    <view class="status-card">
      <view class="status">{{ order.status }}</view>
      <view class="order-no">{{ order.order_no }}</view>
    </view>
    <view class="money-card">
      <view><text>订单金额</text><text>¥{{ (order.total_amount / 100).toFixed(2) }}</text></view>
      <view><text>陪玩收入</text><text>¥{{ (order.player_amount / 100).toFixed(2) }}</text></view>
      <view><text>平台服务费</text><text>¥{{ (order.platform_fee / 100).toFixed(2) }}</text></view>
    </view>
    <button v-if="order.status === 'WAITING_PAYMENT'" class="primary" @click="mockPay">Mock 支付</button>
    <view v-else-if="order.status === 'MATCHING'" class="notice">订单已进入抢单池，切换到陪玩工作台进行抢单。</view>
    <button v-if="order.status === 'FINISH_REQUESTED'" class="primary" @click="confirmFinish">确认完成并结算</button>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.status-card { padding: 38rpx; border-radius: 34rpx; background: #17171f; color: #fff; }
.status { font-size: 42rpx; font-weight: 800; }
.order-no { margin-top: 14rpx; color: #aaaab4; font-size: 20rpx; }
.money-card { margin-top: 24rpx; padding: 28rpx; border-radius: 30rpx; background: #fff; }
.money-card view { display: flex; justify-content: space-between; padding: 16rpx 0; color: #686872; font-size: 24rpx; }
.money-card view text:last-child { color: #15151b; font-weight: 700; }
.primary { margin-top: 28rpx; height: 88rpx; line-height: 88rpx; border-radius: 28rpx; background: #6c5ce7; color: #fff; font-size: 28rpx; font-weight: 700; }
.notice { margin-top: 28rpx; padding: 26rpx; border-radius: 26rpx; background: #f0edff; color: #6c5ce7; font-size: 24rpx; line-height: 1.6; }
</style>
