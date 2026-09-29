<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"
import { request } from "../../api/client"
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
const busy = ref(false)

const nextAction = computed(() => {
  if (order.value?.status === "ACCEPTED") return { label: "开始服务", endpoint: "start" }
  if (order.value?.status === "IN_SERVICE") return { label: "请求结束", endpoint: "finish" }
  return null
})

async function load() {
  if (!orderId.value) return
  order.value = await request<Order>(`/orders/${orderId.value}`)
}

async function act() {
  if (!order.value || !nextAction.value || busy.value) return
  busy.value = true
  try {
    const identities = await getDemoIdentities()
    const userId = identities.players[0]?.userId
    if (!userId) throw new Error("DEMO_PLAYER_NOT_FOUND")
    order.value = await request<Order>(
      `/player/orders/${order.value.id}/${nextAction.value.endpoint}`,
      { method: "POST", userId }
    )
    uni.showToast({ title: nextAction.value.endpoint === "start" ? "服务已开始" : "已请求结束", icon: "success" })
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
  await load()
})
</script>

<template>
  <view v-if="order" class="page">
    <view class="hero">
      <view class="status">{{ order.status }}</view>
      <view class="income">¥{{ (order.player_amount / 100).toFixed(2) }}</view>
      <view class="caption">本单陪玩收入</view>
    </view>

    <view class="card">
      <view><text>订单号</text><b>{{ order.order_no }}</b></view>
      <view><text>用户实付</text><b>¥{{ (order.total_amount / 100).toFixed(2) }}</b></view>
      <view><text>平台服务费</text><b>¥{{ (order.platform_fee / 100).toFixed(2) }}</b></view>
      <view><text>版本</text><b>v{{ order.version }}</b></view>
    </view>

    <button v-if="nextAction" class="primary" :loading="busy" @click="act">
      {{ nextAction.label }}
    </button>
    <view v-else class="notice">
      {{ order.status === "FINISH_REQUESTED" ? "等待用户确认完成并结算。" : "当前没有需要陪玩执行的动作。" }}
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.hero { padding: 40rpx; border-radius: 36rpx; background: #17171f; color: white; }
.status { color: #aaaab4; font-size: 22rpx; }
.income { margin-top: 20rpx; font-size: 58rpx; font-weight: 800; }
.caption { margin-top: 8rpx; color: #aaaab4; font-size: 21rpx; }
.card { margin-top: 24rpx; padding: 30rpx; border-radius: 30rpx; background: white; }
.card view { display: flex; justify-content: space-between; padding: 18rpx 0; font-size: 22rpx; border-bottom: 1rpx solid #f0f0f4; }
.card view:last-child { border: 0; }
.card text { color: #92929d; }
.primary { margin-top: 28rpx; height: 88rpx; line-height: 88rpx; border-radius: 28rpx; background: #6c5ce7; color: white; font-size: 28rpx; font-weight: 700; }
.notice { margin-top: 28rpx; padding: 26rpx; border-radius: 26rpx; background: #f0edff; color: #6c5ce7; font-size: 23rpx; line-height: 1.6; }
</style>
