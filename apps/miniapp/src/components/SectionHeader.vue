<script setup lang="ts">
withDefaults(defineProps<{
  title:string
  subtitle?:string
  action?:string
}>(), {
  subtitle:"",
  action:""
})
defineEmits<{ action:[] }>()
</script>

<template>
  <view class="section-head">
    <view class="copy">
      <text class="title">{{ title }}</text>
      <text v-if="subtitle" class="subtitle">{{ subtitle }}</text>
    </view>
    <text v-if="action" class="action" @click="$emit('action')">{{ action }}</text>
  </view>
</template>

<style scoped>
.section-head { display:flex; align-items:flex-end; justify-content:space-between; gap:24rpx; margin-bottom:22rpx; }
.copy { min-width:0; }
.title { display:block; color:#17171d; font-size:32rpx; font-weight:760; letter-spacing:-.5rpx; }
.subtitle { display:block; margin-top:7rpx; color:#9a9aa4; font-size:20rpx; }
.action { flex:none; color:#6c5ce7; font-size:21rpx; font-weight:600; }
</style>
