<script setup lang="ts">
withDefaults(defineProps<{
  tone?: "neutral" | "brand" | "success" | "warning" | "danger"
  dot?: boolean
}>(), {
  tone: "neutral",
  dot: false
})
</script>

<template>
  <text class="ui-badge" :class="'ui-badge--' + tone">
    <text v-if="dot" class="ui-badge__dot" aria-hidden="true"></text>
    <slot />
  </text>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  gap: 7rpx;
  min-height: 34rpx;
  padding: 4rpx 10rpx;
  border-radius: 999rpx;
  font-size: 16rpx;
  font-weight: 720;
  line-height: 1.2;
  white-space: nowrap;
}

.ui-badge__dot {
  width: 8rpx;
  height: 8rpx;
  flex: none;
  border-radius: 50%;
  background: currentColor;
}

.ui-badge--neutral {
  background: var(--neutral-soft);
  color: var(--neutral);
}

.ui-badge--brand {
  background: var(--brand-soft);
  color: var(--brand);
}

.ui-badge--success {
  background: var(--success-soft);
  color: var(--success);
}

.ui-badge--warning {
  background: var(--warning-soft);
  color: var(--warning);
}

.ui-badge--danger {
  background: var(--danger-soft);
  color: var(--danger);
}
</style>
