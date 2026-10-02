<script setup lang="ts">
import UiButton from "./ui/UiButton.vue"

withDefaults(defineProps<{
  title: string
  description?: string
  symbol?: string
  action?: string
  inverse?: boolean
}>(), {
  description: "",
  symbol: "·",
  action: "",
  inverse: false
})

defineEmits<{ action: [] }>()
</script>

<template>
  <view class="empty" :class="{ inverse }">
    <view class="symbol">{{ symbol }}</view>
    <text class="title">{{ title }}</text>
    <text v-if="description" class="description">{{ description }}</text>
    <view v-if="action" class="action-wrap">
      <UiButton size="sm" variant="secondary" :inverse="inverse" @click="$emit('action')">
        {{ action }}
      </UiButton>
    </view>
  </view>
</template>

<style scoped>
.empty {
  padding: 70rpx 34rpx;
  border: 1rpx solid rgba(20, 20, 30, 0.035);
  border-radius: var(--radius-lg);
  background: var(--surface);
  text-align: center;
  box-shadow: var(--shadow-card);
}

.symbol {
  width: 90rpx;
  height: 90rpx;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 28rpx;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 34rpx;
  font-weight: 800;
}

.title {
  display: block;
  margin-top: 22rpx;
  color: var(--ink);
  font-size: 27rpx;
  font-weight: 780;
}

.description {
  display: block;
  margin: 10rpx auto 0;
  max-width: 500rpx;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.55;
}

.action-wrap {
  margin-top: 24rpx;
}

.empty.inverse {
  border-color: rgba(255, 255, 255, 0.05);
  background: var(--inverse-surface);
  box-shadow: none;
}

.inverse .symbol {
  background: var(--inverse-control-strong);
  color: var(--brand-on-inverse);
}

.inverse .title {
  color: #fff;
}

.inverse .description {
  color: var(--inverse-muted);
}
</style>
