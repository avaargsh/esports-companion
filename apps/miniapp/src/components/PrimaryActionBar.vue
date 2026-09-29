<script setup lang="ts">
withDefaults(defineProps<{primaryText?:string;secondaryText?:string;loading?:boolean;disabled?:boolean;dark?:boolean}>(),{
  primaryText:"",secondaryText:"",loading:false,disabled:false,dark:false
})
defineEmits<{primary:[];secondary:[]}>()
</script>
<template>
  <view v-if="primaryText||secondaryText" class="bar" :class="{dark}">
    <button v-if="secondaryText" class="secondary" :disabled="loading" @click="$emit('secondary')">{{ secondaryText }}</button>
    <button v-if="primaryText" class="primary" :loading="loading" :disabled="disabled||loading" @click="$emit('primary')">{{ primaryText }}</button>
  </view>
</template>
<style scoped>
.bar{position:fixed;z-index:20;left:0;right:0;bottom:0;display:flex;gap:12rpx;padding:16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));border-top:1rpx solid var(--line);background:rgba(255,255,255,.96);backdrop-filter:blur(18rpx)}
.bar.dark{border-top-color:rgba(255,255,255,.06);background:rgba(15,15,21,.96)}
button{height:82rpx;margin:0;line-height:82rpx;border-radius:24rpx;font-size:23rpx;font-weight:780}
.primary{flex:1.45;background:var(--ink);color:#fff}.secondary{flex:1;background:#efeff3;color:#5d5d67}.dark .primary{background:#6757e6}.dark .secondary{background:#24242d;color:#bdbbc7}button[disabled]{opacity:.45}
</style>
