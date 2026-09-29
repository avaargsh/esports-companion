<script setup lang="ts">
withDefaults(defineProps<{
  cents: number
  size?: "sm" | "md" | "lg"
  muted?: boolean
}>(), {
  size: "md",
  muted: false
})
</script>

<template>
  <text class="price" :class="[size, { muted }]">¥{{ (cents / 100).toFixed(2) }}</text>
</template>

<style scoped>
.price { font-variant-numeric: tabular-nums; font-weight: 800; letter-spacing: -.5rpx; }
.price.sm { font-size: 22rpx; }
.price.md { font-size: 30rpx; }
.price.lg { font-size: 40rpx; }
.price.muted { color: #8d8d98; font-weight: 650; }
</style>
