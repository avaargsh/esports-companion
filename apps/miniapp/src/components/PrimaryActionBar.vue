<script setup lang="ts">
import UiButton from "./ui/UiButton.vue"

withDefaults(
  defineProps<{
    primaryText?: string
    secondaryText?: string
    loading?: boolean
    disabled?: boolean
    dark?: boolean
  }>(),
  {
    primaryText: "",
    secondaryText: "",
    loading: false,
    disabled: false,
    dark: false
  }
)

defineEmits<{ primary: []; secondary: [] }>()
</script>

<template>
  <view v-if="primaryText || secondaryText" class="bar" :class="{ dark }">
    <UiButton
      v-if="secondaryText"
      class="secondary"
      variant="secondary"
      :inverse="dark"
      :disabled="loading"
      @click="$emit('secondary')"
    >
      {{ secondaryText }}
    </UiButton>
    <UiButton
      v-if="primaryText"
      class="primary"
      :inverse="dark"
      :loading="loading"
      :disabled="disabled || loading"
      @click="$emit('primary')"
    >
      {{ primaryText }}
    </UiButton>
  </view>
</template>

<style scoped>
.bar {
  position: fixed;
  z-index: 20;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 12rpx;
  padding: 16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid var(--line);
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(18rpx);
}

.bar.dark {
  border-top-color: rgba(255, 255, 255, 0.06);
  background: rgba(15, 15, 21, 0.96);
}

.secondary {
  flex: 1;
}

.primary {
  flex: 1.45;
}
</style>
