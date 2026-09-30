<script setup lang="ts">
const props = withDefaults(defineProps<{
  title: string
  description?: string
  value?: string
  clickable?: boolean
  arrow?: boolean
  disabled?: boolean
}>(), {
  description: "",
  value: "",
  clickable: false,
  arrow: false,
  disabled: false
})

const emit = defineEmits<{ click: [] }>()

function handleClick() {
  if (!props.clickable || props.disabled) return
  emit("click")
}
</script>

<template>
  <view
    class="ui-cell"
    :class="{ 'ui-cell--disabled': disabled }"
    :hover-class="clickable && !disabled ? 'ui-cell--pressed' : 'none'"
    hover-stay-time="80"
    @click="handleClick"
  >
    <view v-if="$slots.icon" class="ui-cell__icon">
      <slot name="icon" />
    </view>

    <view class="ui-cell__main">
      <text class="ui-cell__title">
        <slot name="title">{{ title }}</slot>
      </text>
      <text v-if="description || $slots.description" class="ui-cell__description">
        <slot name="description">{{ description }}</slot>
      </text>
    </view>

    <view v-if="value || $slots.value" class="ui-cell__value">
      <slot name="value">{{ value }}</slot>
    </view>

    <slot name="extra" />

    <text v-if="arrow" class="ui-cell__arrow" aria-hidden="true">›</text>
  </view>
</template>

<style scoped>
.ui-cell {
  min-height: 96rpx;
  padding: 22rpx 24rpx;
  display: flex;
  align-items: center;
  gap: 18rpx;
  background: var(--surface);
  transition:
    background 0.12s ease,
    opacity 0.12s ease;
}

.ui-cell__icon {
  flex: none;
}

.ui-cell__main {
  flex: 1;
  min-width: 0;
}

.ui-cell__title,
.ui-cell__description {
  display: block;
}

.ui-cell__title {
  color: var(--ink);
  font-size: 24rpx;
  font-weight: 720;
  line-height: 1.35;
}

.ui-cell__description {
  margin-top: 6rpx;
  color: var(--muted);
  font-size: 18rpx;
  line-height: 1.5;
}

.ui-cell__value {
  flex: none;
  max-width: 260rpx;
  color: var(--muted);
  font-size: 20rpx;
  text-align: right;
}

.ui-cell__arrow {
  flex: none;
  margin-left: -4rpx;
  color: var(--muted-2);
  font-size: 34rpx;
  line-height: 1;
}

.ui-cell--pressed {
  background: var(--surface-2);
}

.ui-cell--disabled {
  opacity: 0.45;
}

@media (prefers-reduced-motion: reduce) {
  .ui-cell {
    transition: none;
  }
}
</style>
