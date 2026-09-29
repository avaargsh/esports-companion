<script setup lang="ts">
import PriceText from "./PriceText.vue"

withDefaults(defineProps<{
  cents: number
  primaryText: string
  note?: string
  loading?: boolean
  disabled?: boolean
}>(), {
  note: "",
  loading: false,
  disabled: false
})

defineEmits<{ primary: [] }>()
</script>

<template>
  <view class="checkout">
    <view class="summary">
      <text class="label">合计</text>
      <view class="price-row">
        <PriceText :cents="cents" size="lg" />
      </view>
      <text v-if="note" class="note">{{ note }}</text>
    </view>
    <button
      class="primary"
      :loading="loading"
      :disabled="disabled || loading"
      hover-class="pressed"
      @click="$emit('primary')"
    >
      {{ primaryText }}
    </button>
  </view>
</template>

<style scoped>
.checkout {
  position:fixed;
  z-index:30;
  left:0;
  right:0;
  bottom:0;
  display:flex;
  align-items:center;
  gap:22rpx;
  padding:16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  border-top:1rpx solid rgba(20,20,30,.055);
  background:rgba(255,255,255,.97);
  backdrop-filter:blur(20rpx);
  box-shadow:0 -12rpx 36rpx rgba(25,20,55,.045);
}
.summary { flex:1; min-width:0; }
.label { display:block; color:var(--muted); font-size:16rpx; }
.price-row { margin-top:1rpx; line-height:1; }
.note {
  display:block;
  overflow:hidden;
  margin-top:4rpx;
  max-width:330rpx;
  color:var(--muted);
  font-size:15rpx;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.primary {
  width:304rpx;
  height:84rpx;
  margin:0;
  line-height:84rpx;
  border-radius:26rpx;
  background:var(--ink);
  color:#fff;
  font-size:24rpx;
  font-weight:800;
  box-shadow:0 12rpx 28rpx rgba(23,23,31,.12);
}
.primary.pressed { transform:scale(.985); opacity:.92; }
.primary[disabled] { opacity:.38; box-shadow:none; }
</style>
