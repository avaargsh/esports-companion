<script setup lang="ts">
import UiButton from "./ui/UiButton.vue"

withDefaults(defineProps<{
  title: string
  description?: string
  action?: string
}>(), {
  description: "",
  action: ""
})

defineEmits<{ action: [] }>()
</script>

<template>
  <view class="section-head">
    <view class="copy">
      <text class="title">{{ title }}</text>
      <text v-if="description" class="description">{{ description }}</text>
    </view>
    <UiButton
      v-if="action"
      class="action"
      variant="plain"
      size="sm"
      @click="$emit('action')"
    >
      {{ action }}
    </UiButton>
  </view>
</template>

<style scoped>
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  margin-bottom: 22rpx;
}

.copy {
  min-width: 0;
}

.title {
  display: block;
  color: var(--ink);
  font-size: 31rpx;
  font-weight: 800;
  letter-spacing: -0.5rpx;
}

.description {
  display: block;
  margin-top: 7rpx;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.45;
}

.action {
  flex: none;
}
</style>
