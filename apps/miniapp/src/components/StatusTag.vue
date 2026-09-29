<script setup lang="ts">
import { computed } from "vue"
import type { OrderStatus } from "../types/domain"
import { orderStatusMeta, type OrderRole } from "../utils/order"

const props = withDefaults(defineProps<{
  status: OrderStatus
  role?: OrderRole
}>(), {
  role: "CUSTOMER"
})

const meta = computed(() => orderStatusMeta(props.status, props.role))
</script>

<template>
  <text class="tag" :class="meta.tone">{{ meta.label }}</text>
</template>

<style scoped>
.tag { display:inline-flex; align-items:center; padding:9rpx 16rpx; border-radius:999rpx; font-size:20rpx; font-weight:700; }
.tag.neutral { background:#f1f2f5; color:#767681; }
.tag.primary { background:#f0edff; color:#6c5ce7; }
.tag.warning { background:#fff4e5; color:#c77a00; }
.tag.success { background:#eafbf2; color:#1b9658; }
.tag.danger { background:#fff0f0; color:#d94346; }
</style>
