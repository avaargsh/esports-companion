<script setup lang="ts">
withDefaults(defineProps<{
  step: number
  total?: number
  role?: "用户端" | "陪玩端"
  dark?: boolean
  title: string
  description: string
}>(), {
  total: 6,
  role: "用户端",
  dark: false
})
</script>

<template>
  <view class="journey" :class="{ dark }">
    <view class="journey-head">
      <view class="journey-badge">样板体验</view>
      <text class="journey-role">{{ role }}</text>
      <text class="journey-step">{{ step }}/{{ total }}</text>
    </view>
    <text class="journey-title">{{ title }}</text>
    <text class="journey-desc">{{ description }}</text>
    <view class="journey-track">
      <view
        v-for="index in total"
        :key="index"
        class="journey-track-item"
        :class="{ active: index <= step }"
      ></view>
    </view>
  </view>
</template>

<style scoped>
.journey{
  margin-bottom:18rpx;padding:22rpx 24rpx;border:1rpx solid var(--line);
  border-radius:26rpx;background:var(--brand-ghost);box-shadow:var(--shadow-card);
}
.journey-head{display:flex;align-items:center;gap:9rpx}
.journey-badge{padding:6rpx 10rpx;border-radius:999rpx;background:var(--brand);color:#fff;font-size:15rpx;font-weight:800}
.journey-role{color:var(--brand);font-size:16rpx;font-weight:750}
.journey-step{margin-left:auto;color:var(--muted);font-size:16rpx}
.journey-title{display:block;margin-top:15rpx;color:var(--ink);font-size:23rpx;font-weight:800}
.journey-desc{display:block;margin-top:7rpx;color:var(--ink-2);font-size:18rpx;line-height:1.55}
.journey-track{display:flex;gap:7rpx;margin-top:17rpx}
.journey-track-item{height:5rpx;flex:1;border-radius:999rpx;background:var(--line)}
.journey-track-item.active{background:var(--brand)}
.journey.dark{border-color:rgba(0,0,0,.06);background:var(--inverse-surface);box-shadow:none}
.journey.dark .journey-title{color:#fff}
.journey.dark .journey-desc{color:var(--inverse-muted)}
.journey.dark .journey-step{color:#777582}
.journey.dark .journey-track-item{background:var(--inverse-control-strong)}
.journey.dark .journey-track-item.active{background:var(--brand)}
</style>
