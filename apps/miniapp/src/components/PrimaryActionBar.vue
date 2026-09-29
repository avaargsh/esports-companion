<script setup lang="ts">
withDefaults(defineProps<{
  primaryText?: string
  secondaryText?: string
  loading?: boolean
  disabled?: boolean
  dark?: boolean
}>(), {
  primaryText: "",
  secondaryText: "",
  loading: false,
  disabled: false,
  dark: false
})

defineEmits<{
  primary: []
  secondary: []
}>()
</script>

<template>
  <view v-if="primaryText || secondaryText" class="bar" :class="{ dark }">
    <button
      v-if="secondaryText"
      class="secondary"
      :disabled="loading"
      @click="$emit('secondary')"
    >
      {{ secondaryText }}
    </button>
    <button
      v-if="primaryText"
      class="primary"
      :loading="loading"
      :disabled="disabled || loading"
      @click="$emit('primary')"
    >
      {{ primaryText }}
    </button>
  </view>
</template>

<style scoped>
.bar {
  position:fixed;
  z-index:20;
  left:0;
  right:0;
  bottom:0;
  display:flex;
  gap:16rpx;
  padding:18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));
  border-top:1rpx solid #ececf2;
  background:rgba(255,255,255,.96);
  backdrop-filter:blur(18rpx);
}
.bar.dark { border-top-color:rgba(255,255,255,.06); background:rgba(15,15,21,.96); }
button { margin:0; height:84rpx; line-height:84rpx; border-radius:25rpx; font-size:25rpx; font-weight:750; }
.primary { flex:1.4; background:#6c5ce7; color:#fff; }
.secondary { flex:1; background:#f1f1f5; color:#555560; }
.dark .secondary { background:#24242d; color:#bdbdc7; }
button[disabled] { opacity:.5; }
</style>
