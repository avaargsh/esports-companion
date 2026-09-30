<script setup lang="ts">
const props = withDefaults(defineProps<{
  variant?: "primary" | "secondary" | "danger" | "plain"
  size?: "md" | "sm"
  block?: boolean
  loading?: boolean
  disabled?: boolean
  inverse?: boolean
}>(), {
  variant: "primary",
  size: "md",
  block: false,
  loading: false,
  disabled: false,
  inverse: false
})

const emit = defineEmits<{ click: [] }>()

function handleClick() {
  if (props.disabled || props.loading) return
  emit("click")
}
</script>

<template>
  <button
    class="ui-button"
    :class="[
      'ui-button--' + variant,
      'ui-button--' + size,
      {
        'ui-button--block': block,
        'ui-button--inverse': inverse
      }
    ]"
    :loading="loading"
    :disabled="disabled"
    :hover-class="disabled || loading ? 'none' : 'ui-button--pressed'"
    hover-stay-time="80"
    @click="handleClick"
  >
    <slot />
  </button>
</template>

<style scoped>
.ui-button {
  min-width: 160rpx;
  min-height: var(--control-height);
  margin: 0;
  padding: 0 28rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  border-radius: var(--radius-md);
  font-size: 22rpx;
  font-weight: 760;
  line-height: 1.2;
  transition:
    transform 0.12s ease,
    opacity 0.12s ease,
    background 0.12s ease;
}

.ui-button--block {
  width: 100%;
}

.ui-button--sm {
  min-width: 120rpx;
  min-height: var(--control-height-sm);
  padding: 0 20rpx;
  border-radius: 20rpx;
  font-size: 20rpx;
}

.ui-button--primary {
  background: var(--brand);
  color: #fff;
}

.ui-button--secondary {
  border: 1rpx solid var(--line);
  background: var(--surface);
  color: var(--ink);
}

.ui-button--secondary.ui-button--inverse {
  border-color: rgba(255, 255, 255, 0.06);
  background: var(--inverse-control-strong);
  color: var(--inverse-text-soft);
}

.ui-button--danger {
  background: var(--danger);
  color: #fff;
}

.ui-button--plain {
  min-width: auto;
  padding-right: 0;
  padding-left: 0;
  background: transparent;
  color: var(--brand);
}

.ui-button[disabled] {
  opacity: 0.45;
}

.ui-button--pressed {
  transform: scale(0.985);
  opacity: 0.9;
}

@media (prefers-reduced-motion: reduce) {
  .ui-button {
    transition: none;
  }
}
</style>
