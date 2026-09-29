<script setup lang="ts">
import { computed } from "vue"
import type { Order } from "../types/domain"
import { orderStatusMeta } from "../utils/order"
const props=defineProps<{order:Order}>()
const emit=defineEmits<{(event:"open",order:Order):void}>()
const meta=computed(()=>orderStatusMeta(props.order.status))
</script>

<template>
  <view class="card tap-scale" @click="emit('open',order)">
    <view class="top">
      <view>
        <text class="number">{{ order.order_no }}</text>
        <text class="status" :class="meta.tone">{{ meta.label }}</text>
      </view>
      <text class="amount"><small>¥</small>{{ (order.total_amount/100).toFixed(2) }}</text>
    </view>
    <text class="description">{{ meta.description }}</text>
    <view class="bottom">
      <view class="progress"><view class="bar" :class="meta.tone" :style="{width:meta.progress+'%'}"></view></view>
      <text class="chevron">›</text>
    </view>
  </view>
</template>

<style scoped>
.card {
  padding:25rpx 26rpx;border:1rpx solid rgba(20,20,30,.035);border-radius:30rpx;
  background:#fff;box-shadow:var(--shadow-card);
}
.top { display:flex;align-items:flex-start;justify-content:space-between;gap:20rpx; }
.number { display:block;color:var(--muted);font-size:17rpx; }
.status { display:block;margin-top:8rpx;font-size:27rpx;font-weight:800; }
.status.primary{color:var(--brand)} .status.success{color:var(--success)}
.status.warning{color:var(--warning)} .status.danger{color:var(--danger)} .status.neutral{color:#70707b}
.amount { flex:none;color:var(--ink);font-size:29rpx;font-weight:850; }
.amount small { font-size:17rpx; }
.description { display:block;margin-top:11rpx;color:var(--muted);font-size:19rpx; }
.bottom { display:flex;align-items:center;gap:16rpx;margin-top:22rpx; }
.progress { flex:1;height:7rpx;overflow:hidden;border-radius:999rpx;background:#efeff3; }
.bar { height:100%;border-radius:999rpx;background:var(--brand); }
.bar.success{background:var(--success)} .bar.warning{background:#d59b37}.bar.danger{background:var(--danger)}.bar.neutral{background:#a4a4ae}
.chevron { color:#c0c0c8;font-size:29rpx; }
</style>
