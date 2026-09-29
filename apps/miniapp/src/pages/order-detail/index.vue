<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onUnload } from "@dcloudio/uni-app"

import { API_ORIGIN, request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order } from "../../types/domain"
import { orderStatusMeta } from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const customerUserId = ref("")
const socketConnected = ref(false)
const busy = ref(false)
const rating = ref(5)
const review = ref("")
const reviewed = ref(false)
const aftercareReason = ref("")
let socket: UniApp.SocketTask | null = null

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status) : null
)

async function reload() {
  if (!orderId.value) return
  order.value = await request<Order>(`/orders/${orderId.value}`, { userId: customerUserId.value })
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
      // Ignore development messages that are not JSON.
    }
  })
}

onLoad(async query => {
  orderId.value = String(query?.id ?? "")
  const identities = await getDemoIdentities()
  customerUserId.value = identities.customer.userId
  await reload()
  connectRealtime()
})

onUnload(() => socket?.close({}))

async function run(action: "pay" | "cancel" | "confirm") {
  if (!order.value || busy.value) return
  busy.value = true
  try {
    if (action === "pay") {
      order.value = await request<Order>(
        `/orders/${order.value.id}/mock-pay`,
        {
          method: "POST",
          userId: customerUserId.value,
          headers: { "Idempotency-Key": `miniapp-${order.value.id}` }
        }
      )
      uni.showToast({ title: "支付成功", icon: "success" })
    }

    if (action === "cancel") {
      order.value = await request<Order>(
        `/orders/${order.value.id}/cancel`,
        {
          method: "POST",
          userId: customerUserId.value
        }
      )
    }

    if (action === "confirm") {
      order.value = await request<Order>(
        `/orders/${order.value.id}/confirm`,
        {
          method: "POST",
          userId: customerUserId.value
        }
      )
      uni.showToast({ title: "已确认完成", icon: "success" })
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

async function requestAftercare(action: "refund" | "dispute") {
  if (!order.value || busy.value) return
  busy.value = true
  try {
    await request(
      `/orders/${order.value.id}/disputes`,
      {
        method: "POST",
        userId: customerUserId.value,
        headers: { "Idempotency-Key": `miniapp-dispute-${order.value.id}` },
        data: {
          reason_code: action === "refund" ? "CANCEL_BEFORE_SERVICE" : "SERVICE_ISSUE",
          description: aftercareReason.value.trim()
        }
      }
    )
    aftercareReason.value = ""
    uni.showToast({
      title: action === "refund" ? "退款申请已提交，等待平台处理" : "已申请平台介入",
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
  if (!order.value || reviewed.value || busy.value) return
  busy.value = true
  try {
    await request(`/orders/${order.value.id}/reviews`, {
      method: "POST",
      userId: customerUserId.value,
      data: {
        rating: rating.value,
        content: review.value.trim()
      }
    })
    reviewed.value = true
    uni.showToast({ title: "感谢你的评价", icon: "success" })
  } catch (error) {
    const message = error instanceof Error ? error.message : "评价失败"
    if (message === "ORDER_ALREADY_REVIEWED") reviewed.value = true
    uni.showToast({ title: message, icon: "none" })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <view v-if="order && meta" class="page">
    <view class="status-card">
      <view class="live-row">
        <text class="live-dot" :class="{ online: socketConnected }">●</text>
        <text>{{ socketConnected ? "实时更新已连接" : "正在连接实时状态" }}</text>
      </view>
      <view class="status">{{ meta.label }}</view>
      <view class="description">{{ meta.description }}</view>
      <view class="progress">
        <view class="bar" :style="{ width: meta.progress + '%' }" />
      </view>
      <view class="order-no">{{ order.order_no }}</view>
    </view>

    <view v-if="order.service_player" class="section-card provider-card">
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
      </view>
    </view>

    <view class="section-card">
      <view class="section-title">费用明细</view>
      <view class="row">
        <text>服务金额</text>
        <text class="strong">¥{{ (order.total_amount / 100).toFixed(2) }}</text>
      </view>
    </view>

    <view v-if="order.status === 'MATCHING'" class="notice">
      <text class="notice-title">正在为你匹配</text>
      <text>订单已进入陪玩抢单池，接单后这里会自动更新，无需手动刷新。</text>
    </view>

    <view v-if="order.status === 'WAITING_PAYMENT' && order.designated_player_id" class="notice designated">
      <text class="notice-title">已锁定指定大神</text>
      <text>支付成功后将直接绑定该大神，不进入公开抢单池。</text>
    </view>

    <view v-if="order.status === 'ACCEPTED'" class="notice success">
      <text class="notice-title">陪玩已接单</text>
      <text>等待陪玩开始服务；服务开始后状态会自动更新。</text>
    </view>

    <view v-if="order.status === 'WAITING_PAYMENT'" class="actions">
      <button class="ghost" :disabled="busy" @click="run('cancel')">取消订单</button>
      <button class="primary" :loading="busy" @click="run('pay')">支付并开始匹配</button>
    </view>

    <button
      v-if="order.status === 'FINISH_REQUESTED'"
      class="primary full"
      :loading="busy"
      @click="run('confirm')"
    >
      确认服务完成
    </button>

    <view
      v-if="order.available_actions?.includes('REQUEST_REFUND') || order.available_actions?.includes('OPEN_DISPUTE')"
      class="section-card aftercare-card"
    >
      <view class="section-title">需要帮助？</view>
      <view class="aftercare-hint">
        退款和服务争议都会进入平台审核；审核通过后再执行退款或继续结算。
      </view>
      <textarea
        v-model="aftercareReason"
        maxlength="500"
        placeholder="简单说明原因，便于平台后续处理"
      />
      <view class="aftercare-actions">
        <button
          v-if="order.available_actions?.includes('REQUEST_REFUND')"
          class="ghost danger"
          :disabled="busy"
          @click="requestAftercare('refund')"
        >
          申请退款
        </button>
        <button
          v-if="order.available_actions?.includes('OPEN_DISPUTE')"
          class="ghost"
          :disabled="busy"
          @click="requestAftercare('dispute')"
        >
          申请平台介入
        </button>
      </view>
    </view>

    <view v-if="order.status === 'SETTLED' && !reviewed" class="section-card review-card">
      <view class="section-title">评价本次服务</view>
      <view class="stars">
        <text
          v-for="value in 5"
          :key="value"
          :class="{ active: value <= rating }"
          @click="rating = value"
        >★</text>
      </view>
      <textarea
        v-model="review"
        maxlength="1000"
        placeholder="说说这次陪玩体验，可选"
      />
      <button class="primary full" :loading="busy" @click="submitReview">提交评价</button>
    </view>

    <view v-else-if="reviewed" class="reviewed">评价已提交，感谢反馈。</view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx 28rpx 60rpx; }
.status-card { padding: 38rpx; border-radius: 34rpx; background: linear-gradient(145deg,#17171f,#29263a); color: #fff; }
.live-row { display: flex; align-items: center; gap: 8rpx; color: #aaaab4; font-size: 20rpx; }
.live-dot { color: #64646f; }
.live-dot.online { color: #47d182; }
.status { margin-top: 30rpx; font-size: 44rpx; font-weight: 800; }
.description { margin-top: 10rpx; color: #c3c3cc; font-size: 23rpx; }
.progress { margin-top: 26rpx; height: 9rpx; overflow: hidden; border-radius: 999rpx; background: rgba(255,255,255,.11); }
.bar { height: 100%; border-radius: 999rpx; background: linear-gradient(90deg,#8b7cf6,#69ddd7); }
.order-no { margin-top: 20rpx; color: #858590; font-size: 19rpx; }
.section-card { margin-top: 22rpx; padding: 30rpx; border-radius: 30rpx; background: #fff; }
.section-title { font-size: 28rpx; font-weight: 700; }
.provider-row { display: flex; align-items: center; gap: 20rpx; margin-top: 20rpx; }
.provider-avatar { width: 86rpx; height: 86rpx; border-radius: 26rpx; flex-shrink: 0; }
.provider-avatar.fallback { display: flex; align-items: center; justify-content: center; background: #17171f; color: #fff; font-size: 30rpx; font-weight: 800; }
.provider-copy { flex: 1; min-width: 0; }
.provider-name { font-size: 27rpx; font-weight: 700; }
.provider-meta { margin-top: 8rpx; color: #92929d; font-size: 20rpx; }
.row { display: flex; justify-content: space-between; align-items: center; margin-top: 22rpx; color: #686872; font-size: 24rpx; }
.strong { color: #15151b; font-size: 31rpx; font-weight: 800; }
.notice { margin-top: 22rpx; padding: 28rpx; border-radius: 28rpx; background: #f0edff; color: #6c5ce7; font-size: 23rpx; line-height: 1.6; }
.notice.success { background: #eafbf2; color: #16824d; }
.notice.designated { background: #fff6e7; color: #9a6417; }
.notice-title { display: block; margin-bottom: 6rpx; font-weight: 700; }
.actions { margin-top: 26rpx; display: flex; gap: 18rpx; }
.actions button { flex: 1; margin: 0; }
.primary, .ghost { height: 86rpx; line-height: 86rpx; border-radius: 26rpx; font-size: 26rpx; font-weight: 700; }
.primary { background: #6c5ce7; color: #fff; }
.ghost { background: #fff; color: #686872; }
.ghost.danger { color: #d05252; border: 1rpx solid #f2d2d2; }
.aftercare-hint { color: #92929d; font-size: 21rpx; line-height: 1.6; }
.aftercare-card textarea { width: 100%; height: 130rpx; margin-top: 18rpx; padding: 18rpx; border-radius: 20rpx; background: #f7f7fb; box-sizing: border-box; font-size: 22rpx; }
.aftercare-actions { display: flex; gap: 16rpx; margin-top: 16rpx; }
.aftercare-actions button { flex: 1; margin: 0; }
.full { margin-top: 26rpx; width: 100%; }
.review-card textarea { width: 100%; height: 150rpx; margin-top: 18rpx; padding: 18rpx; border-radius: 20rpx; background: #f7f7fb; box-sizing: border-box; font-size: 23rpx; }
.stars { margin-top: 18rpx; display: flex; gap: 12rpx; }
.stars text { color: #d6d6de; font-size: 52rpx; }
.stars text.active { color: #f0b72f; }
.reviewed { margin-top: 24rpx; padding: 26rpx; border-radius: 26rpx; background: #eafbf2; color: #16824d; text-align: center; font-size: 23rpx; }
</style>
