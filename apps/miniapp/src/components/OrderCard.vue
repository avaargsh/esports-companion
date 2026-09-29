<script setup lang="ts">
import { computed } from "vue"

import type { Order } from "../types/domain"
import { orderStatusMeta } from "../utils/order"

const props = defineProps<{ order: Order }>()
const emit = defineEmits<{ (event: "open", order: Order): void }>()

const meta = computed(() => orderStatusMeta(props.order.status))
</script>

<template>
  <view class="card" @click="emit('open', order)">
    <view class="head">
      <text class="number">{{ order.order_no }}</text>
      <text class="status" :class="meta.tone">{{ meta.label }}</text>
    </view>

    <view class="body">
      <view class="state">
        <text class="hint">{{ meta.description }}</text>
        <view class="progress">
          <view class="bar" :style="{ width: meta.progress + '%' }" />
        </view>
      </view>
      <text class="amount">¥{{ (order.total_amount / 100).toFixed(2) }}</text>
    </view>
  </view>
</template>

<style scoped>
.card { padding: 28rpx; border-radius: 30rpx; background: #fff; box-shadow: 0 12rpx 40rpx rgba(25,20,60,.045); }
.head, .body { display: flex; align-items: center; justify-content: space-between; gap: 24rpx; }
.number { color: #686872; font-size: 22rpx; }
.status { padding: 7rpx 14rpx; border-radius: 999rpx; font-size: 20rpx; }
.status.primary { background: #f0edff; color: #6c5ce7; }
.status.success { background: #eafbf2; color: #22a665; }
.status.warning { background: #fff7e8; color: #c77a00; }
.status.danger { background: #fff0f0; color: #d94346; }
.status.neutral { background: #f2f3f5; color: #777781; }
.body { margin-top: 24rpx; }
.state { flex: 1; min-width: 0; }
.hint { color: #92929d; font-size: 21rpx; }
.progress { margin-top: 14rpx; height: 8rpx; overflow: hidden; border-radius: 999rpx; background: #eeeef4; }
.bar { height: 100%; border-radius: 999rpx; background: #6c5ce7; }
.amount { flex: none; font-size: 30rpx; font-weight: 800; }
</style>
