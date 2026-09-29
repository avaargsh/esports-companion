<script setup lang="ts">
import { computed } from "vue"
import type { Order } from "../types/domain"

const props = defineProps<{ order:Order; actionText?:string }>()
defineEmits<{ action:[order:Order] }>()

const labels:Record<string,string> = {
  WAITING_PAYMENT:"待支付", PAID:"已支付", MATCHING:"匹配中", ACCEPTED:"已接单",
  IN_SERVICE:"服务中", FINISH_REQUESTED:"待确认", COMPLETED:"已完成",
  SETTLED:"已结算", CANCELLED:"已取消", REFUNDING:"退款中", REFUNDED:"已退款", DISPUTED:"争议中"
}

const statusTone = computed(() => {
  if (["COMPLETED","SETTLED"].includes(props.order.status)) return "success"
  if (["CANCELLED","REFUNDED","DISPUTED"].includes(props.order.status)) return "danger"
  if (["WAITING_PAYMENT","FINISH_REQUESTED","REFUNDING"].includes(props.order.status)) return "warning"
  return "brand"
})
</script>

<template>
  <view class="card pressable">
    <view class="head">
      <view>
        <text class="eyebrow">订单</text>
        <text class="no">{{ order.order_no }}</text>
      </view>
      <text class="status" :class="statusTone">{{ labels[order.status] || order.status }}</text>
    </view>

    <view class="meta-row">
      <view class="meta-chip">× {{ order.quantity }}</view>
      <view class="meta-chip">版本 {{ order.version }}</view>
      <view class="meta-chip">平台担保</view>
    </view>

    <view class="bottom">
      <view>
        <text class="price-label">订单金额</text>
        <text class="amount">¥{{ (order.total_amount / 100).toFixed(2) }}</text>
      </view>
      <button v-if="actionText" class="action" @click.stop="$emit('action', order)">{{ actionText }}</button>
    </view>
  </view>
</template>

<style scoped>
.card {
  padding: 30rpx;
  border: 1rpx solid rgba(20,20,28,.035);
  border-radius: 32rpx;
  background: #fff;
  box-shadow: 0 14rpx 42rpx rgba(27,22,60,.065);
}
.head,.bottom { display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.eyebrow { display:block; color:#a0a0aa; font-size:18rpx; letter-spacing:2rpx; }
.no { display:block; margin-top:6rpx; color:#4f4f5a; font-size:22rpx; }
.status { flex:none; padding:9rpx 16rpx; border-radius:999rpx; font-size:20rpx; font-weight:650; }
.status.brand { background:#f1efff; color:#6c5ce7; }
.status.success { background:#ebfbf2; color:#1c9a58; }
.status.warning { background:#fff7e7; color:#c57a00; }
.status.danger { background:#fff0f0; color:#dc3f3f; }
.meta-row { display:flex; gap:10rpx; flex-wrap:wrap; margin:26rpx 0 30rpx; }
.meta-chip { padding:8rpx 14rpx; border-radius:999rpx; background:#f7f7fa; color:#7e7e88; font-size:20rpx; }
.price-label { display:block; color:#9a9aa4; font-size:19rpx; }
.amount { display:block; margin-top:4rpx; color:#17171d; font-size:38rpx; font-weight:800; letter-spacing:-1rpx; }
.action {
  margin:0;
  min-width:156rpx;
  height:68rpx;
  line-height:68rpx;
  border-radius:22rpx;
  background:#17171f;
  color:white;
  font-size:22rpx;
  font-weight:650;
}
</style>
