<script setup lang="ts">
import { computed } from "vue"
import type { OrderStatus } from "../types/domain"
import { orderStatusMeta,type OrderRole } from "../utils/order"
const props=withDefaults(defineProps<{status:OrderStatus;role?:OrderRole;dark?:boolean}>(),{role:"CUSTOMER",dark:false})
const labels=["下单","支付","接单","服务","完成"]
const meta=computed(()=>orderStatusMeta(props.status,props.role))
</script>
<template>
  <view class="wrap" :class="{dark}">
    <view class="rail">
      <view v-for="step in 5" :key="step" class="step">
        <view class="node" :class="{active:step<=meta.step,danger:meta.tone==='danger'&&step===meta.step}"></view>
        <view v-if="step<5" class="line" :class="{active:step<meta.step}"></view>
      </view>
    </view>
    <view class="labels"><text v-for="label in labels" :key="label">{{ label }}</text></view>
  </view>
</template>
<style scoped>
.rail{display:flex;align-items:center}.step{flex:1;display:flex;align-items:center}.step:last-child{flex:0}.node{width:14rpx;height:14rpx;flex:none;border:4rpx solid #e7e6ed;border-radius:50%;background:#fff}.node.active{border-color:var(--brand);background:var(--brand)}.node.danger{border-color:var(--danger);background:var(--danger)}.line{height:3rpx;flex:1;background:#e8e7ed}.line.active{background:var(--brand)}.labels{display:flex;justify-content:space-between;margin-top:10rpx;color:#aaa9b3;font-size:14rpx}.dark .node{border-color:rgba(255,255,255,.13);background:#2b2937}.dark .node.active{border-color:#9688ef;background:#9688ef}.dark .line{background:rgba(255,255,255,.09)}.dark .line.active{background:#8173df}.dark .labels{color:#777482}
</style>
