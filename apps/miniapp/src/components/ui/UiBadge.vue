<script setup lang="ts">
withDefaults(defineProps<{
  tone?: "neutral" | "brand" | "success" | "warning" | "danger"
}>(), {
  tone: "neutral"
})
</script>

<template>
  <text class="ui-badge" :class="'ui-badge--' + tone">
    <slot />
  </text>
</template>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  min-height: 34rpx;
  padding: 4rpx 10rpx;
  border-radius: 999rpx;
  font-size: 16rpx;
  font-weight: 720;
  line-height: 1.2;
  white-space: nowrap;
}

.ui-badge--neutral {
  background: #f3f3f6;
  color: #686873;
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
