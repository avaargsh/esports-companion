<script setup lang="ts">
import { onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import { usePlayerWithdrawals } from "../../features/wallet/usePlayerWithdrawals"

const {
  wallet,
  items,
  amountYuan,
  busy,
  loadStatus,
  loadMessage,
  amountCents,
  requestEnabled,
  canSubmit,
  pendingAmount,
  load,
  submit,
  withdrawAll,
  copyValue,
  statusLabel,
  formatTime
} = usePlayerWithdrawals()

onShow(() => {
  void load()
})
</script>

<template>
  <view class="page">
    <EmptyState
      v-if="loadStatus === 'error'"
      title="收益账户暂时没加载出来"
      :description="loadMessage"
      action="重新加载"
      symbol="↻"
      inverse
      @action="load"
    />

    <view v-if="loadStatus !== 'error'" class="balance-card">
      <view class="eyebrow">收益账户</view>
      <view class="balance-label">可提现余额</view>
      <view class="balance">¥{{ (wallet.availableBalance / 100).toFixed(2) }}</view>
      <view class="balance-meta">
        <text>冻结 ¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</text>
        <text>待处理提现 ¥{{ (pendingAmount / 100).toFixed(2) }}</text>
      </view>
    </view>

    <view v-if="loadStatus !== 'error'" class="form-card">
      <view class="form-head">
        <view>
          <view class="title">申请提现</view>
          <view class="hint">提交后由平台审核并打款，处理中金额会暂时冻结。</view>
        </view>
        <text v-if="requestEnabled" class="all" @click="withdrawAll">全部提现</text>
      </view>

      <view class="amount-input">
        <text>¥</text>
        <input
          v-model="amountYuan"
          type="digit"
          placeholder="0.00"
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

    <view v-if="loadStatus !== 'error'" class="history">
      <view class="history-head">
        <view class="title">提现记录</view>
        <text>{{ items.length }} 笔</text>
      </view>

      <view v-if="loadStatus === 'loading'" class="empty">正在同步钱包…</view>
      <view v-else-if="!items.length" class="empty">暂无提现记录</view>

      <view v-for="item in items" :key="item.id" class="item">
        <view>
          <view class="item-amount">¥{{ (item.amount / 100).toFixed(2) }}</view>
          <view class="item-time">{{ formatTime(item.created_at) }}</view>
          <view class="reference-row" @click="copyValue(item.id, '申请号')">
            <text>申请号 {{ item.id.slice(0,8) }}</text><text class="copy">复制</text>
          </view>
          <view v-if="item.provider_txn_id" class="reference-row payout" @click="copyValue(item.provider_txn_id, '打款参考号')">
            <text class="reference-value">打款参考号 {{ item.provider_txn_id }}</text><text class="copy">复制</text>
          </view>
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
.page{min-height:100vh;padding:28rpx;background:var(--inverse-bg);color:#fff}.balance-card{position:relative;overflow:hidden;padding:32rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:34rpx;background:linear-gradient(145deg,#1b1a23,#2b263f)}.eyebrow{color:#77728d;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.balance-label{margin-top:24rpx;color:#8d8a98;font-size:18rpx}.balance{margin-top:5rpx;font-size:55rpx;font-weight:850;letter-spacing:-1rpx}.balance-meta{display:flex;justify-content:space-between;gap:15rpx;margin-top:24rpx;padding-top:19rpx;border-top:1rpx solid rgba(255,255,255,.06);color:#777582;font-size:16rpx}
.form-card,.history{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:28rpx;background:var(--inverse-surface)}.form-head,.history-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx}.title{font-size:24rpx;font-weight:780}.hint{margin-top:6rpx;color:#777582;font-size:17rpx;line-height:1.5}.all{flex:none;color:var(--brand-on-inverse);font-size:18rpx;font-weight:700}.amount-input{display:flex;align-items:center;margin-top:22rpx;padding:17rpx 20rpx;border-radius:21rpx;background:var(--inverse-control)}.amount-input text{color:#aaa5ca;font-size:30rpx;font-weight:800}.amount-input input{flex:1;margin-left:11rpx;color:#fff;font-size:38rpx;font-weight:820}.error{margin-top:9rpx;color:var(--danger-on-inverse);font-size:16rpx}.submit{height:76rpx;margin:18rpx 0 0;line-height:76rpx;border-radius:22rpx;background:var(--brand);color:#fff;font-size:21rpx;font-weight:760}.submit[disabled]{background:#292832;color:#666471;opacity:1}.rules{display:grid;gap:6rpx;margin-top:19rpx;color:#696773;font-size:16rpx;line-height:1.5}.history-head text{color:#777582;font-size:17rpx}.item{display:flex;align-items:center;justify-content:space-between;gap:16rpx;padding:20rpx 0;border-top:1rpx solid rgba(255,255,255,.05)}.item:first-of-type{margin-top:13rpx}.item-amount{font-size:24rpx;font-weight:780}.item-time{margin-top:5rpx;color:#696773;font-size:15rpx}.reference-row{display:flex;align-items:center;gap:9rpx;max-width:500rpx;margin-top:7rpx;color:#898694;font-size:15rpx}.reference-row.payout{color:#9e96cd}.reference-value{max-width:390rpx;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.copy{flex:none;color:var(--brand-on-inverse);font-weight:700}.reason{margin-top:5rpx;color:#b56c70;font-size:15rpx}.status{flex:none;padding:7rpx 11rpx;border-radius:999rpx;background:#26252e;color:#9997a2;font-size:16rpx}.status.pending{background:rgba(211,148,38,.1);color:var(--warning-on-inverse)}.status.completed{background:rgba(39,187,111,.1);color:var(--success-on-inverse)}.status.rejected{background:rgba(239,68,68,.09);color:var(--danger-on-inverse)}.empty{padding:54rpx 0 24rpx;color:#6d6b77;text-align:center;font-size:18rpx}
</style>