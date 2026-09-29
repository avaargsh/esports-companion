<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

const profile = ref<Player | null>(null)
const balance = ref(0)
const playerUserId = ref("")
const busy = ref(false)

const online = computed(() => profile.value?.service_status === "AVAILABLE")

async function load() {
  const identities = await getDemoIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  if (!playerUserId.value) return
  profile.value = await request<Player>("/player/profile", { userId: playerUserId.value })
  const wallet = await request<{ availableBalance: number }>("/wallet", {
    userId: playerUserId.value
  })
  balance.value = wallet.availableBalance
}

async function toggleStatus() {
  if (!profile.value || !playerUserId.value || busy.value) return
  busy.value = true
  try {
    profile.value = await request<Player>("/player/profile", {
      method: "PATCH",
      userId: playerUserId.value,
      data: { service_status: online.value ? "OFFLINE" : "AVAILABLE" }
    })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "状态切换失败",
      icon: "none"
    })
  } finally {
    busy.value = false
  }
}

function openPool() {
  uni.navigateTo({ url: "/pages-player/order-pool/index" })
}

function openOrders() {
  uni.navigateTo({ url: "/pages-player/orders/index" })
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="summary">
      <view class="topline">
        <view>
          <text class="label">可提现收益</text>
          <view class="amount">¥ {{ (balance / 100).toFixed(2) }}</view>
        </view>
        <view class="status" :class="{ off: !online }" @click="toggleStatus">
          ● {{ online ? "接单中" : "已下线" }}
        </view>
      </view>

      <view class="identity">
        <view class="player-name">{{ profile?.display_name || "Demo Player" }}</view>
        <view class="verify">认证：{{ profile?.verification_status || "-" }}</view>
      </view>

      <view class="actions">
        <button class="primary" @click="openPool">去抢单</button>
        <button class="secondary" @click="openOrders">服务订单</button>
      </view>
    </view>

    <view class="tip">
      Demo 模式使用第一个已审核陪玩账号。抢单成功后可继续 Start → Finish。
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.summary { padding: 36rpx; border-radius: 36rpx; background: #17171f; color: white; }
.topline { display: flex; justify-content: space-between; align-items: flex-start; }
.label { color: #aaaab4; font-size: 22rpx; }
.amount { margin-top: 12rpx; font-size: 54rpx; font-weight: 800; }
.status { padding: 12rpx 18rpx; border-radius: 999rpx; background: rgba(34,197,94,.14); color: #5ddb8b; font-size: 22rpx; }
.status.off { background: rgba(255,255,255,.08); color: #aaaab4; }
.identity { margin-top: 42rpx; padding-top: 30rpx; border-top: 1rpx solid rgba(255,255,255,.08); }
.player-name { font-size: 30rpx; font-weight: 700; }
.verify { margin-top: 8rpx; color: #aaaab4; font-size: 21rpx; }
.actions { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; margin-top: 32rpx; }
.primary, .secondary { height: 84rpx; line-height: 84rpx; border-radius: 26rpx; font-size: 25rpx; font-weight: 700; }
.primary { background: #6c5ce7; color: white; }
.secondary { background: rgba(255,255,255,.08); color: white; }
.tip { margin-top: 24rpx; padding: 24rpx; border-radius: 26rpx; background: white; color: #92929d; font-size: 21rpx; line-height: 1.6; }
</style>
