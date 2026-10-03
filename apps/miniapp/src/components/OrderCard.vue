<script setup lang="ts">
import { computed } from "vue"
import type { Order } from "../types/domain"
import { orderStatusMeta } from "../utils/order"

const props = defineProps<{ order: Order }>()
const emit = defineEmits<{ (event: "open", order: Order): void }>()
const meta = computed(() => orderStatusMeta(props.order.status))
const statusCode = computed(() => props.order.statusCode || props.order.status_code || props.order.status)
const waitingMatch = computed(() => ["MATCHING", "PAID"].includes(String(statusCode.value)))
const gameName = computed(() => {
  const extra = props.order as Order & { game_name?: string; sku_name?: string }
  return extra.game_name || extra.sku_name || "电竞陪玩"
})
const gameIconUrl = computed(() => {
  const extra = props.order as Order & { game_icon_url?: string; icon_url?: string }
  return extra.game_icon_url || extra.icon_url || "https://img.icons8.com/fluency/96/controller.png"
})
</script>

<template>
  <view class="card tap-scale" @click="emit('open', order)">
    <view class="top">
      <view class="game">
        <view class="game-icon"><image :src="gameIconUrl" mode="aspectFit" /></view>
        <view class="game-copy">
          <text class="game-name">{{ gameName }}</text>
          <text class="number">{{ order.order_no }}</text>
        </view>
      </view>
      <text class="amount">¥{{ (order.total_amount / 100).toFixed(2) }}</text>
    </view>

    <view class="status-row">
      <text class="status" :class="meta.tone">{{ meta.label }}</text>
      <text v-if="waitingMatch" class="live-badge"><text class="breath"></text>优先推送中</text>
    </view>

    <text class="description">
      {{ waitingMatch ? "订单已优先推送至优质大神抢单大厅" : meta.description }}
    </text>

    <view class="bottom">
      <view class="progress" :class="{ waiting: waitingMatch }">
        <view class="bar" :class="meta.tone" :style="{ width: meta.progress + '%' }"></view>
      </view>
      <text class="chevron">›</text>
    </view>

    <view class="actions">
      <button class="ghost" @click.stop="emit('open', order)">取消订单</button>
      <button class="ghost support" @click.stop="emit('open', order)">联系客服</button>
    </view>
  </view>
</template>

<style scoped>
.card{padding:26rpx;border:1rpx solid rgba(0,0,0,.09);border-radius:32rpx;background:#ffffff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.08)}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:20rpx}.game{display:flex;align-items:center;gap:15rpx;min-width:0}.game-icon{width:58rpx;height:58rpx;flex:none;display:flex;align-items:center;justify-content:center;border:1rpx solid rgba(0,0,0,.12);border-radius:18rpx;background:linear-gradient(135deg,#111827,#000000);box-shadow:0 10rpx 26rpx rgba(0,0,0,.10)}.game-icon image{width:40rpx;height:40rpx}.game-copy{min-width:0}.game-name{display:block;overflow:hidden;color:#111827;font-size:23rpx;font-weight:900;text-overflow:ellipsis;white-space:nowrap}.number{display:block;margin-top:5rpx;color:#6b7280;font-size:15rpx}.amount{flex:none;color:#111827;font-size:31rpx;font-weight:950}.status-row{display:flex;align-items:center;gap:10rpx;margin-top:22rpx}.status{font-size:26rpx;font-weight:900}.status.primary,.status.warning{color:#111827}.status.success{color:#111827}.status.danger{color:#111827}.status.neutral{color:#6b7280}.live-badge{display:flex;align-items:center;gap:7rpx;padding:6rpx 11rpx;border-radius:999rpx;background:rgba(0,0,0,.07);color:#111827;font-size:15rpx;font-weight:850}.breath{width:10rpx;height:10rpx;border-radius:50%;background:#111827;animation:pulse 1.5s infinite}@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(0,0,0,.22)}70%{box-shadow:0 0 0 16rpx rgba(0,0,0,0)}100%{box-shadow:0 0 0 0 rgba(0,0,0,0)}}.description{display:block;margin-top:10rpx;color:#6b7280;font-size:19rpx;line-height:1.45}.bottom{display:flex;align-items:center;gap:16rpx;margin-top:22rpx}.progress{position:relative;flex:1;height:9rpx;overflow:hidden;border-radius:999rpx;background:#f3f4f6}.progress.waiting::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(0,0,0,.10),transparent);animation:wave 1.4s infinite}@keyframes wave{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}.bar{height:100%;border-radius:999rpx;background:#111827}.bar.success{background:#111827}.bar.warning{background:#111827}.bar.danger{background:#111827}.bar.neutral{background:#6b7280}.chevron{color:#6b7280;font-size:31rpx}.actions{display:flex;gap:12rpx;margin-top:22rpx}.ghost{height:56rpx;line-height:56rpx;margin:0;padding:0 18rpx;border-radius:999rpx;background:#f3f4f6;color:#374151;font-size:18rpx;font-weight:780}.ghost.support{border:1rpx solid rgba(0,0,0,.08);background:rgba(0,0,0,.05);color:#111827}
</style>
