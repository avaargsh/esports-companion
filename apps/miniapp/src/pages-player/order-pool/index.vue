<script setup lang="ts">
import { computed, ref } from "vue"
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import StatusTag from "../../components/StatusTag.vue"
import type { Game, Order } from "../../types/domain"
import { claimErrorMessage } from "../../utils/order"

type Player = {
  id: string
  user_id: string
  display_name: string
  verification_status: string
  service_status: string
}

const games = ref<Game[]>([])
const selectedGameId = ref("")
const orders = ref<Order[]>([])
const profile = ref<Player | null>(null)
const playerUserId = ref("")
const loading = ref(false)
const claimingId = ref("")

const totalIncome = computed(() =>
  orders.value.reduce((sum, item) => sum + item.player_amount, 0)
)

const canClaim = computed(() =>
  profile.value?.verification_status === "APPROVED" &&
  profile.value?.service_status === "AVAILABLE"
)

const claimBlockReason = computed(() => {
  if (!profile.value) return "正在同步陪玩身份"
  if (profile.value.verification_status !== "APPROVED") return "认证未通过，暂不可接单"
  if (profile.value.service_status !== "AVAILABLE") return "当前已暂停接单，请先回工作台开启接单"
  return ""
})

async function refresh() {
  if (!selectedGameId.value) return
  loading.value = true
  try {
    orders.value = await request<Order[]>(
      `/player/order-pool?game_id=${selectedGameId.value}`
    )
  } catch (error) {
    orders.value = []
    uni.showToast({
      title: error instanceof Error ? error.message : "订单池加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

async function bootstrap() {
  try {
    const identities = await getDemoIdentities()
    playerUserId.value = identities.players[0]?.userId ?? ""
    if (!playerUserId.value) throw new Error("PLAYER_PROFILE_NOT_FOUND")

    const [profileResult, gameResult] = await Promise.all([
      request<Player>("/player/profile", { userId: playerUserId.value }),
      request<Game[]>("/games")
    ])
    profile.value = profileResult
    games.value = gameResult

    if (!selectedGameId.value && games.value.length) {
      selectedGameId.value = games.value[0].id
    }
    await refresh()
  } catch (error) {
    uni.showToast({
      title: claimErrorMessage(error instanceof Error ? error.message : ""),
      icon: "none"
    })
  }
}

async function selectGame(id: string) {
  if (selectedGameId.value === id) return
  selectedGameId.value = id
  await refresh()
}

async function claim(order: Order) {
  if (!playerUserId.value || claimingId.value) return
  if (!canClaim.value) {
    uni.showToast({ title: claimBlockReason.value, icon: "none" })
    return
  }

  claimingId.value = order.id
  try {
    const claimed = await request<Order>(`/player/orders/${order.id}/claim`, {
      method: "POST",
      userId: playerUserId.value,
      data: { expected_version: order.version }
    })
    uni.showToast({ title: "接单成功", icon: "success" })
    uni.navigateTo({ url: `/pages-player/order-detail/index?id=${claimed.id}` })
  } catch (error) {
    uni.showToast({
      title: claimErrorMessage(error instanceof Error ? error.message : ""),
      icon: "none"
    })
    await refresh()
  } finally {
    claimingId.value = ""
  }
}

onShow(() => { void bootstrap() })

onPullDownRefresh(async () => {
  await refresh()
  uni.stopPullDownRefresh()
})
</script>

<template>
  <view class="page">
    <view class="heading">
      <view>
        <text class="eyebrow">LIVE ORDER POOL</text>
        <view class="title">抢单大厅</view>
      </view>
      <view class="live"><text class="dot"></text>实时订单</view>
    </view>

    <view v-if="claimBlockReason" class="guard" :class="{ ok: canClaim }">
      <text>{{ canClaim ? "当前可接单" : claimBlockReason }}</text>
      <text class="guard-link" @click="uni.navigateBack()">返回工作台 ›</text>
    </view>

    <view class="overview">
      <view><text class="num">{{ orders.length }}</text><text class="label">可抢订单</text></view>
      <view><text class="num">¥{{ (totalIncome/100).toFixed(0) }}</text><text class="label">池内预估收益</text></view>
      <view><text class="num">保护</text><text class="label">安全抢单</text></view>
    </view>

    <scroll-view scroll-x class="filter" :show-scrollbar="false">
      <view class="filter-row">
        <text
          v-for="game in games"
          :key="game.id"
          :class="{ active:selectedGameId===game.id }"
          @click="selectGame(game.id)"
        >{{ game.name }}</text>
      </view>
    </scroll-view>

    <view v-if="loading" class="tip">正在刷新订单池…</view>
    <view v-else-if="!orders.length" class="empty">
      <view class="empty-icon">⌁</view>
      <view class="empty-title">当前没有新订单</view>
      <view class="empty-desc">下拉或点击按钮刷新，不需要反复退出页面。</view>
      <button class="ghost" @click="refresh">刷新订单池</button>
    </view>

    <view v-for="order in orders" :key="order.id" class="order-card">
      <view class="head">
        <view class="order-copy">
          <view class="badges">
            <StatusTag :status="order.status" role="PLAYER" />
            <text>平台担保</text>
          </view>
          <view class="game">订单 {{ order.order_no }}</view>
          <view class="meta">数量 × {{ order.quantity || 1 }}</view>
        </view>
        <view class="income">
          <text>预计收入</text>
          <view>¥{{ (order.player_amount/100).toFixed(2) }}</view>
        </view>
      </view>

      <view class="fee-row">
        <text>订单总额 ¥{{ (order.total_amount/100).toFixed(2) }}</text>
        <text>平台费 ¥{{ (order.platform_fee/100).toFixed(2) }}</text>
      </view>

      <button
        class="claim"
        :disabled="!canClaim || !!claimingId"
        @click="claim(order)"
      >
        {{ claimingId===order.id ? "抢单中…" : canClaim ? "立即抢单" : "暂不可接单" }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#101016; color:#fff; }
.heading { display:flex; justify-content:space-between; align-items:flex-end; padding:14rpx 2rpx 22rpx; }
.eyebrow { color:#777783; font-size:17rpx; letter-spacing:3rpx; }
.title { margin-top:7rpx; font-size:38rpx; font-weight:850; }
.live { display:flex; align-items:center; gap:8rpx; padding:9rpx 14rpx; border-radius:999rpx; background:rgba(34,197,94,.12); color:#61d88e; font-size:19rpx; }
.dot { width:12rpx; height:12rpx; border-radius:50%; background:#36d178; box-shadow:0 0 16rpx rgba(54,209,120,.9); }
.guard { display:flex; justify-content:space-between; gap:16rpx; margin-bottom:18rpx; padding:18rpx 20rpx; border-radius:20rpx; background:rgba(245,158,11,.12); color:#e5ad55; font-size:19rpx; }
.guard.ok { background:rgba(34,197,94,.10); color:#5edb8d; }
.guard-link { flex:none; color:#a99df6; font-weight:700; }
.overview { display:flex; margin-bottom:22rpx; padding:24rpx 12rpx; border:1rpx solid rgba(255,255,255,.05); border-radius:28rpx; background:#181820; }
.overview view { flex:1; text-align:center; }
.num { display:block; font-size:28rpx; font-weight:800; }
.label { display:block; margin-top:5rpx; color:#777783; font-size:16rpx; }
.filter { width:100%; margin-bottom:20rpx; }
.filter-row { display:flex; gap:10rpx; white-space:nowrap; }
.filter-row>text { flex:none; padding:14rpx 20rpx; border-radius:18rpx; background:#1b1b24; color:#858590; font-size:21rpx; }
.filter-row .active { background:#6c5ce7; color:#fff; font-weight:700; }
.order-card { margin-bottom:16rpx; padding:28rpx; border:1rpx solid rgba(255,255,255,.05); border-radius:32rpx; background:#191920; box-shadow:0 16rpx 40rpx rgba(0,0,0,.12); }
.head { display:flex; justify-content:space-between; gap:18rpx; }
.order-copy { min-width:0; }
.badges { display:flex; align-items:center; gap:8rpx; margin-bottom:16rpx; }
.badges>text { padding:7rpx 12rpx; border-radius:999rpx; background:#262631; color:#aaaab7; font-size:17rpx; }
.game { overflow:hidden; font-size:25rpx; font-weight:750; white-space:nowrap; text-overflow:ellipsis; }
.meta { margin-top:8rpx; color:#70707c; font-size:18rpx; }
.income { flex:none; text-align:right; }
.income text { display:block; color:#7d7d88; font-size:16rpx; }
.income view { margin-top:5rpx; color:#9b8cff; font-size:32rpx; font-weight:850; }
.fee-row { display:flex; gap:20rpx; margin-top:24rpx; padding:18rpx 0; border-top:1rpx solid rgba(255,255,255,.05); color:#777783; font-size:18rpx; }
.claim { margin-top:6rpx; height:78rpx; line-height:78rpx; border-radius:24rpx; background:#6c5ce7; color:#fff; font-size:24rpx; font-weight:750; }
.claim[disabled] { background:#2a2932; color:#686873; opacity:1; }
.tip { padding:90rpx 0; text-align:center; color:#777783; font-size:21rpx; }
.empty { padding:88rpx 20rpx; text-align:center; }
.empty-icon { width:108rpx; height:108rpx; margin:auto; display:flex; align-items:center; justify-content:center; border-radius:34rpx; background:#1d1d26; color:#8172ec; font-size:42rpx; }
.empty-title { margin-top:24rpx; font-size:28rpx; font-weight:750; }
.empty-desc { margin-top:10rpx; color:#747480; font-size:20rpx; }
.ghost { margin:26rpx auto 0; width:220rpx; height:70rpx; line-height:70rpx; border-radius:20rpx; background:#24242e; color:#c7c7d0; font-size:21rpx; }
</style>
