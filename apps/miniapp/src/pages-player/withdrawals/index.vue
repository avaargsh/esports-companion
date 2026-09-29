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
      <view class="eyebrow">收益账户</view>
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
          <view class="hint">提交后由平台审核并打款，处理中金额会暂时冻结。</view>
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
.page{min-height:100vh;padding:28rpx;background:#101016;color:#fff}.balance-card{position:relative;overflow:hidden;padding:32rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:34rpx;background:linear-gradient(145deg,#1b1a23,#2b263f)}.eyebrow{color:#77728d;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.balance-label{margin-top:24rpx;color:#8d8a98;font-size:18rpx}.balance{margin-top:5rpx;font-size:55rpx;font-weight:850;letter-spacing:-1rpx}.balance-meta{display:flex;justify-content:space-between;gap:15rpx;margin-top:24rpx;padding-top:19rpx;border-top:1rpx solid rgba(255,255,255,.06);color:#777582;font-size:16rpx}
.form-card,.history{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:28rpx;background:#191920}.form-head,.history-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx}.title{font-size:24rpx;font-weight:780}.hint{margin-top:6rpx;color:#777582;font-size:17rpx;line-height:1.5}.all{flex:none;color:#a99cf7;font-size:18rpx;font-weight:700}.amount-input{display:flex;align-items:center;margin-top:22rpx;padding:17rpx 20rpx;border-radius:21rpx;background:#23232c}.amount-input text{color:#aaa5ca;font-size:30rpx;font-weight:800}.amount-input input{flex:1;margin-left:11rpx;color:#fff;font-size:38rpx;font-weight:820}.error{margin-top:9rpx;color:#dc7779;font-size:16rpx}.submit{height:76rpx;margin:18rpx 0 0;line-height:76rpx;border-radius:22rpx;background:#6757e6;color:#fff;font-size:21rpx;font-weight:760}.submit[disabled]{background:#292832;color:#666471;opacity:1}.rules{display:grid;gap:6rpx;margin-top:19rpx;color:#696773;font-size:16rpx;line-height:1.5}.history-head text{color:#777582;font-size:17rpx}.item{display:flex;align-items:center;justify-content:space-between;gap:16rpx;padding:20rpx 0;border-top:1rpx solid rgba(255,255,255,.05)}.item:first-of-type{margin-top:13rpx}.item-amount{font-size:24rpx;font-weight:780}.item-time{margin-top:5rpx;color:#696773;font-size:15rpx}.reason{margin-top:5rpx;color:#b56c70;font-size:15rpx}.status{flex:none;padding:7rpx 11rpx;border-radius:999rpx;background:#26252e;color:#9997a2;font-size:16rpx}.status.pending{background:rgba(211,148,38,.1);color:#d9aa59}.status.completed{background:rgba(39,187,111,.1);color:#5ed28e}.status.rejected{background:rgba(239,68,68,.09);color:#dc7779}.empty{padding:54rpx 0 24rpx;color:#6d6b77;text-align:center;font-size:18rpx}
</style>