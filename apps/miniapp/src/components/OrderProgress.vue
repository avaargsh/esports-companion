<script setup lang="ts">
import { computed } from "vue"
import type { OrderStatus } from "../types/domain"
import { orderStatusMeta, type OrderRole } from "../utils/order"

const props = withDefaults(defineProps<{
  status: OrderStatus
  role?: OrderRole
  dark?: boolean
}>(), {
  role: "CUSTOMER",
  dark: false
})

const labels = ["下单", "支付/匹配", "接单", "服务", "完成"]
const meta = computed(() => orderStatusMeta(props.status, props.role))
</script>

<template>
  <view class="progress-wrap" :class="{ dark }">
    <view class="rail">
      <view
        v-for="step in 5"
        :key="step"
        class="node"
        :class="{ active: step <= meta.step, danger: meta.tone === 'danger' && step === meta.step }"
      />
    </view>
    <view class="labels">
      <text v-for="label in labels" :key="label">{{ label }}</text>
    </view>
  </view>
</template>

<style scoped>
.rail { display:flex; gap:8rpx; }
.node { flex:1; height:8rpx; border-radius:999rpx; background:#e9e9ef; }
.node.active { background:#6c5ce7; }
.node.danger { background:#e24b4f; }
.labels { display:flex; justify-content:space-between; margin-top:10rpx; color:#aaaab3; font-size:16rpx; }
.dark .node { background:rgba(255,255,255,.10); }
.dark .node.active { background:#9182f5; }
.dark .labels { color:#747480; }
</style>
