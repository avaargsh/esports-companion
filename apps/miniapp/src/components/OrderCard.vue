<script setup lang="ts">
import type { Order } from "../types/domain"
import PriceText from "./PriceText.vue"
import StatusTag from "./StatusTag.vue"

defineProps<{ order: Order }>()
const emit = defineEmits<{
  open: [order: Order]
}>()
</script>

<template>
  <view class="card pressable" @click="emit('open', order)">
    <view class="head">
      <view>
        <text class="eyebrow">订单</text>
        <text class="no">{{ order.order_no }}</text>
      </view>
      <StatusTag :status="order.status" role="CUSTOMER" />
    </view>

    <view class="meta-row">
      <view class="meta-chip">数量 × {{ order.quantity || 1 }}</view>
      <view class="meta-chip">平台担保</view>
    </view>

    <view class="bottom">
      <view>
        <text class="price-label">实付金额</text>
        <PriceText :cents="order.total_amount" size="lg" />
      </view>
      <text class="open">查看详情 ›</text>
    </view>
  </view>
</template>

<style scoped>
.card {
  padding:30rpx;
  border:1rpx solid rgba(20,20,28,.035);
  border-radius:32rpx;
  background:#fff;
  box-shadow:0 14rpx 42rpx rgba(27,22,60,.065);
}
.head,.bottom { display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.eyebrow { display:block; color:#a0a0aa; font-size:18rpx; letter-spacing:2rpx; }
.no { display:block; margin-top:6rpx; color:#4f4f5a; font-size:22rpx; }
.meta-row { display:flex; gap:10rpx; flex-wrap:wrap; margin:26rpx 0 30rpx; }
.meta-chip { padding:8rpx 14rpx; border-radius:999rpx; background:#f7f7fa; color:#7e7e88; font-size:20rpx; }
.price-label { display:block; margin-bottom:4rpx; color:#9a9aa4; font-size:19rpx; }
.open { color:#6c5ce7; font-size:21rpx; font-weight:650; }
</style>
