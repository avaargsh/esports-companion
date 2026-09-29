<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Wallet, Withdrawal } from "../../types/domain"

const userId = ref("")
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
const items = ref<Withdrawal[]>([])
const amountYuan = ref("")
const loading = ref(true)
const busy = ref(false)
const pendingIdempotencyKey = ref("")

const amountCents = computed(() => {
  const value = Number(amountYuan.value)
  if (!Number.isFinite(value) || value <= 0) return 0
  return Math.round(value * 100)
})

const canSubmit = computed(() =>
  amountCents.value > 0 &&
  amountCents.value <= wallet.value.availableBalance &&
  !busy.value
)

const pendingAmount = computed(() =>
  items.value
    .filter(item => item.status === "PENDING")
    .reduce((sum,item)=>sum+item.amount,0)
)

function statusLabel(status: string) {
  const labels: Record<string,string> = {
    PENDING: "审核 / 打款中",
    COMPLETED: "已到账",
    REJECTED: "已退回"
  }
  return labels[status] || status
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleString()
}

async function load() {
  loading.value = true
  try {
    const identities = await getDemoIdentities()
    userId.value = identities.players[0]?.userId ?? ""
    if (!userId.value) throw new Error("PLAYER_REQUIRED")

    const [nextWallet, nextItems] = await Promise.all([
      request<Wallet>("/wallet", { userId: userId.value }),
      request<Withdrawal[]>("/withdrawals", { userId: userId.value })
    ])
    wallet.value = nextWallet
    items.value = nextItems
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "提现信息加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!canSubmit.value || !userId.value) return
  if (!pendingIdempotencyKey.value) {
    pendingIdempotencyKey.value = `miniapp-withdraw-${Date.now()}-${amountCents.value}`
  }

  busy.value = true
  try {
    await request<Withdrawal>("/withdrawals", {
      method: "POST",
      userId: userId.value,
      headers: { "Idempotency-Key": pendingIdempotencyKey.value },
      data: { amount: amountCents.value }
    })
    amountYuan.value = ""
    pendingIdempotencyKey.value = ""
    uni.showToast({ title: "提现申请已提交", icon: "success" })
    await load()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "提交失败，可直接重试",
      icon: "none"
    })
  } finally {
    busy.value = false
  }
}

function withdrawAll() {
  amountYuan.value = (wallet.value.availableBalance / 100).toFixed(2)
  pendingIdempotencyKey.value = ""
}

onShow(() => { void load() })
</script>

<template>
  <view class="page">
    <view class="balance-card">
      <view class="eyebrow">PLAYER WALLET</view>
      <view class="balance-label">可提现余额</view>
      <view class="balance">¥{{ (wallet.availableBalance / 100).toFixed(2) }}</view>
      <view class="balance-meta">
        <text>冻结 ¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</text>
        <text>待处理提现 ¥{{ (pendingAmount / 100).toFixed(2) }}</text>
      </view>
    </view>

    <view class="form-card">
      <view class="form-head">
        <view>
          <view class="title">申请提现</view>
          <view class="hint">v0.4 采用平台人工审核 / 人工打款，申请后金额会立即冻结。</view>
        </view>
        <text class="all" @click="withdrawAll">全部提现</text>
      </view>

      <view class="amount-input">
        <text>¥</text>
        <input
          v-model="amountYuan"
          type="digit"
          placeholder="0.00"
          @input="pendingIdempotencyKey = ''"
        />
      </view>
      <view v-if="amountCents > wallet.availableBalance" class="error">超过当前可提现余额</view>

      <button
        class="submit"
        :disabled="!canSubmit"
        :loading="busy"
        @click="submit"
      >提交提现申请</button>

      <view class="rules">
        <text>• 只有已结算到可用余额的收入可以提现</text>
        <text>• 申请后资金从“可用”转入“冻结”，不会重复扣款</text>
        <text>• 运营拒绝后原金额自动退回可用余额</text>
      </view>
    </view>

    <view class="history">
      <view class="history-head">
        <view class="title">提现记录</view>
        <text>{{ items.length }} 笔</text>
      </view>

      <view v-if="loading" class="empty">正在同步钱包…</view>
      <view v-else-if="!items.length" class="empty">暂无提现记录</view>

      <view v-for="item in items" :key="item.id" class="item">
        <view>
          <view class="item-amount">¥{{ (item.amount / 100).toFixed(2) }}</view>
          <view class="item-time">{{ formatTime(item.created_at) }}</view>
          <view v-if="item.failure_reason" class="reason">{{ item.failure_reason }}</view>
        </view>
        <view class="status" :class="item.status.toLowerCase()">
          {{ statusLabel(item.status) }}
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#0f0f15; color:#fff; box-sizing:border-box; }
.balance-card { padding:38rpx; border-radius:36rpx; background:linear-gradient(145deg,#27233a,#17171f); }
.eyebrow { color:#8579d8; font-size:17rpx; font-weight:800; letter-spacing:3rpx; }
.balance-label { margin-top:28rpx; color:#9b9ba6; font-size:21rpx; }
.balance { margin-top:8rpx; font-size:62rpx; font-weight:850; }
.balance-meta { display:flex; justify-content:space-between; gap:16rpx; margin-top:30rpx; padding-top:24rpx; border-top:1rpx solid rgba(255,255,255,.08); color:#858590; font-size:19rpx; }
.form-card,.history { margin-top:22rpx; padding:30rpx; border-radius:30rpx; background:#181820; }
.form-head,.history-head { display:flex; align-items:flex-start; justify-content:space-between; gap:20rpx; }
.title { font-size:27rpx; font-weight:800; }
.hint { margin-top:8rpx; color:#777783; font-size:19rpx; line-height:1.55; }
.all { flex:none; color:#9b8cff; font-size:20rpx; font-weight:700; }
.amount-input { display:flex; align-items:center; margin-top:26rpx; padding:20rpx 24rpx; border-radius:24rpx; background:#22222b; }
.amount-input text { color:#bbb7d7; font-size:34rpx; font-weight:800; }
.amount-input input { flex:1; margin-left:14rpx; color:#fff; font-size:42rpx; font-weight:800; }
.error { margin-top:10rpx; color:#dc7779; font-size:18rpx; }
.submit { margin:22rpx 0 0; height:82rpx; line-height:82rpx; border-radius:24rpx; background:#6c5ce7; color:#fff; font-size:24rpx; font-weight:750; }
.submit[disabled] { background:#2a2932; color:#666671; opacity:1; }
.rules { display:grid; gap:8rpx; margin-top:24rpx; color:#6f6f7a; font-size:18rpx; line-height:1.5; }
.history-head text { color:#777783; font-size:19rpx; }
.item { display:flex; align-items:center; justify-content:space-between; gap:18rpx; padding:24rpx 0; border-top:1rpx solid rgba(255,255,255,.06); }
.item:first-of-type { margin-top:16rpx; }
.item-amount { font-size:27rpx; font-weight:800; }
.item-time { margin-top:6rpx; color:#6f6f7a; font-size:17rpx; }
.reason { margin-top:6rpx; color:#b86e70; font-size:17rpx; }
.status { flex:none; padding:9rpx 14rpx; border-radius:999rpx; background:#2a2932; color:#aaaab4; font-size:18rpx; }
.status.pending { background:rgba(245,158,11,.12); color:#e0ad58; }
.status.completed { background:rgba(34,197,94,.12); color:#62d38c; }
.status.rejected { background:rgba(239,68,68,.10); color:#d8787a; }
.empty { padding:60rpx 0 30rpx; color:#6f6f7a; text-align:center; font-size:20rpx; }
</style>
