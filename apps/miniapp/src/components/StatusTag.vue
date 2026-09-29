<script setup lang="ts">
import { computed } from "vue"
import type { OrderStatus } from "../types/domain"
import { orderStatusMeta,type OrderRole } from "../utils/order"
const props=withDefaults(defineProps<{status:OrderStatus;role?:OrderRole}>(),{role:"CUSTOMER"})
const meta=computed(()=>orderStatusMeta(props.status,props.role))
</script>
<template><text class="tag" :class="meta.tone"><i></i>{{ meta.label }}</text></template>
<style scoped>
.tag{display:inline-flex;align-items:center;gap:7rpx;padding:7rpx 12rpx;border-radius:999rpx;font-size:17rpx;font-weight:750}.tag i{width:8rpx;height:8rpx;border-radius:50%;background:currentColor}.neutral{background:#f0f0f3;color:#74747f}.primary{background:var(--brand-soft);color:var(--brand)}.warning{background:var(--warning-soft);color:var(--warning)}.success{background:var(--success-soft);color:var(--success)}.danger{background:var(--danger-soft);color:var(--danger)}
</style>
