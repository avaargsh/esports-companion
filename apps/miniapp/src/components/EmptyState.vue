<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  description?: string
  symbol?: string
  action?: string
}>(), {
  description: "",
  symbol: "·",
  action: ""
})
defineEmits<{ action: [] }>()
</script>

<template>
  <view class="empty">
    <view class="symbol">{{ symbol }}</view>
    <text class="title">{{ title }}</text>
    <text v-if="description" class="description">{{ description }}</text>
    <button v-if="action" class="action" @click="$emit('action')">{{ action }}</button>
  </view>
</template>

<style scoped>
.empty {
  padding:70rpx 34rpx;
  border:1rpx solid rgba(20,20,30,.035);
  border-radius:32rpx;
  background:#fff;
  text-align:center;
  box-shadow:var(--shadow-card);
}
.symbol {
  width:90rpx;
  height:90rpx;
  margin:0 auto;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius:28rpx;
  background:var(--brand-soft);
  color:var(--brand);
  font-size:34rpx;
  font-weight:800;
}
.title {
  display:block;
  margin-top:22rpx;
  color:var(--ink);
  font-size:27rpx;
  font-weight:780;
}
.description {
  display:block;
  margin:10rpx auto 0;
  max-width:500rpx;
  color:var(--muted);
  font-size:20rpx;
  line-height:1.55;
}
.action {
  width:230rpx;
  height:70rpx;
  margin:24rpx auto 0;
  line-height:70rpx;
  border-radius:22rpx;
  background:var(--ink);
  color:#fff;
  font-size:21rpx;
  font-weight:750;
}
</style>
