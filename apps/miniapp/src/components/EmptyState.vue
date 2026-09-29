<script setup lang="ts">
withDefaults(defineProps<{
  icon?:string
  title:string
  description?:string
  actionText?:string
}>(), {
  icon:"✦",
  description:"",
  actionText:""
})
defineEmits<{ action:[] }>()
</script>

<template>
  <view class="empty">
    <view class="icon">{{ icon }}</view>
    <text class="title">{{ title }}</text>
    <text v-if="description" class="desc">{{ description }}</text>
    <button v-if="actionText" class="action" @click="$emit('action')">{{ actionText }}</button>
  </view>
</template>

<style scoped>
.empty { padding:88rpx 28rpx; text-align:center; }
.icon { width:112rpx; height:112rpx; margin:0 auto; display:flex; align-items:center; justify-content:center; border-radius:34rpx; background:#f1efff; color:#6c5ce7; font-size:42rpx; font-weight:800; }
.title { display:block; margin-top:28rpx; color:#1a1a21; font-size:30rpx; font-weight:750; }
.desc { display:block; max-width:480rpx; margin:12rpx auto 0; color:#9696a1; font-size:22rpx; line-height:1.6; }
.action { margin:28rpx auto 0; width:240rpx; height:72rpx; line-height:72rpx; border-radius:22rpx; background:#17171f; color:#fff; font-size:23rpx; }
</style>
