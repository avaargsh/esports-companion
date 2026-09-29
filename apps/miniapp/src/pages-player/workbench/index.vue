<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getRuntimeIdentities } from "../../api/identity"
import type { Wallet } from "../../types/domain"
import OfferingPanel from "./OfferingPanel.vue"
import SkillPanel from "./SkillPanel.vue"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

const profile = ref<Player | null>(null)
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
const playerUserId = ref("")
const busy = ref(false)

const online = computed(() => profile.value?.service_status === "AVAILABLE")

async function load() {
  const identities = await getRuntimeIdentities()
  playerUserId.value = identities.players[0]?.userId ?? ""
  if (!playerUserId.value) return

  const [profileResult, walletResult] = await Promise.all([
    request<Player>("/player/profile", { userId: playerUserId.value }),
    request<Wallet>("/wallet", { userId: playerUserId.value })
  ])
  profile.value = profileResult
  wallet.value = walletResult
}

async function toggleStatus() {
  if (!profile.value || !playerUserId.value || busy.value) return
  busy.value = true
  try {
    profile.value = await request<Player>("/player/profile", {
      method: "PUT",
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
          <text class="label">可用收益</text>
          <view class="amount">¥ {{ (wallet.availableBalance / 100).toFixed(2) }}</view>
        </view>
        <view class="status" :class="{ off: !online }" @click="toggleStatus">
          ● {{ online ? "接单中" : "已下线" }}
        </view>
      </view>

      <view class="identity">
        <view>
          <view class="player-name">{{ profile?.display_name || "Demo Player" }}</view>
          <view class="verify">
            {{ profile?.verification_status === "APPROVED" ? "已认证陪玩" : "认证状态：" + (profile?.verification_status || "-") }}
          </view>
        </view>
        <view class="frozen">
          <text>冻结中</text>
          <b>¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</b>
        </view>
      </view>

      <view class="actions">
        <button class="primary" @click="openPool">去抢单</button>
        <button class="secondary" @click="openOrders">服务订单</button>
      </view>
    </view>

    <OfferingPanel v-if="playerUserId" :user-id="playerUserId" />
    <SkillPanel v-if="playerUserId" :user-id="playerUserId" />

    <view class="principle">
      <text class="principle-title">工作台只放履约信息</text>
      <text>抢单、服务状态和收益优先；营销内容留在用户端。</text>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 28rpx; background: #0f0f15; box-sizing: border-box; }
.summary { padding: 36rpx; border-radius: 36rpx; background: linear-gradient(145deg,#1a1922,#242131); color: #fff; }
.topline { display: flex; justify-content: space-between; align-items: flex-start; }
.label { color: #aaaab4; font-size: 22rpx; }
.amount { margin-top: 12rpx; font-size: 54rpx; font-weight: 800; }
.status { padding: 12rpx 18rpx; border-radius: 999rpx; background: rgba(34,197,94,.14); color: #5ddb8b; font-size: 22rpx; }
.status.off { background: rgba(255,255,255,.08); color: #aaaab4; }
.identity { margin-top: 42rpx; padding-top: 30rpx; border-top: 1rpx solid rgba(255,255,255,.08); display: flex; align-items: flex-end; justify-content: space-between; gap: 20rpx; }
.player-name { font-size: 30rpx; font-weight: 700; }
.verify { margin-top: 8rpx; color: #aaaab4; font-size: 21rpx; }
.frozen { text-align: right; color: #777784; font-size: 19rpx; }
.frozen text, .frozen b { display: block; }
.frozen b { margin-top: 5rpx; color: #c8c4dc; font-size: 24rpx; }
.actions { display: flex; gap: 16rpx; margin-top: 32rpx; }
.actions button { flex: 1; margin: 0; }
.primary, .secondary { height: 84rpx; line-height: 84rpx; border-radius: 26rpx; font-size: 25rpx; font-weight: 700; }
.primary { background: #6c5ce7; color: #fff; }
.secondary { background: rgba(255,255,255,.08); color: #fff; }
.principle { margin-top: 24rpx; padding: 26rpx; border-radius: 26rpx; background: #181820; color: #777784; font-size: 21rpx; line-height: 1.6; }
.principle-title { display: block; margin-bottom: 6rpx; color: #c2c2ca; font-weight: 700; }
</style>
