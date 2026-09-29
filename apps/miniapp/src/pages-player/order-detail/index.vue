<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad, onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import OrderProgress from "../../components/OrderProgress.vue"
import PriceText from "../../components/PriceText.vue"
import PrimaryActionBar from "../../components/PrimaryActionBar.vue"
import StatusTag from "../../components/StatusTag.vue"
import type { Order } from "../../types/domain"
import {
  orderStatusMeta,
  playerActionErrorMessage
} from "../../utils/order"

const orderId = ref("")
const order = ref<Order | null>(null)
const playerUserId = ref("")
const busy = ref(false)
const loading = ref(true)

const meta = computed(() =>
  order.value ? orderStatusMeta(order.value.status, "PLAYER") : null
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

async function load() {
  if (!orderId.value) return
  try {
    order.value = await request<Order>(`/orders/${orderId.value}`)
  } catch (error) {
    uni.showToast({
      title: playerActionErrorMessage(error instanceof Error ? error.message : ""),
      icon: "none"
    })
  } finally {
    loading.value = false
  }
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
    uni.showToast({
      title: action.endpoint === "start" ? "服务已开始" : "已申请完成",
      icon: "success"
    })
  } catch (error) {
    uni.showToast({
      title: playerActionErrorMessage(error instanceof Error ? error.message : ""),
      icon: "none"
    })
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
})

onShow(() => {
  if (orderId.value && !loading.value) void load()
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
        <view class="caption">本单预计 / 已结算收入</view>
        <view class="state-desc">{{ meta.description }}</view>
        <OrderProgress :status="order.status" role="PLAYER" dark />
      </view>

      <view class="card">
        <view><text>用户实付</text><PriceText :cents="order.total_amount" size="sm" /></view>
        <view><text>平台服务费</text><PriceText :cents="order.platform_fee" size="sm" muted /></view>
        <view><text>服务数量</text><text class="value">× {{ order.quantity || 1 }}</text></view>
      </view>

      <view v-if="order.status === 'FINISH_REQUESTED'" class="notice">
        已申请完成，正在等待用户确认。确认后平台会进入结算流程。
      </view>
      <view v-else-if="order.status === 'SETTLED'" class="notice success">
        本单已完成结算，收入已进入账本。
      </view>
      <view v-else-if="order.status === 'DISPUTED'" class="notice danger">
        订单正在售后处理中，请等待平台处理，不要继续执行履约动作。
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
.card>view { display:flex; justify-content:space-between; align-items:center; gap:20rpx; padding:18rpx 0; font-size:22rpx; border-bottom:1rpx solid rgba(255,255,255,.06); }
.card>view:last-child { border:0; }
.card text { color:#777784; }
.value { color:#d2d2da !important; font-weight:650; }
.notice { margin-top:22rpx; padding:26rpx; border-radius:26rpx; background:#221f31; color:#b3accf; font-size:21rpx; line-height:1.6; }
.notice.success { background:rgba(34,197,94,.10); color:#64cf8e; }
.notice.danger { background:rgba(239,68,68,.10); color:#dc7779; }
.bottom-spacer { height:126rpx; }
</style>
