<script setup lang="ts">
import { computed } from "vue"
import type { PublicPlayer } from "../types/domain"

const props = defineProps<{ player: PublicPlayer; gameId?: string }>()
defineEmits<{ open: [] }>()

const offering = computed(() => {
  const filtered = props.gameId
    ? props.player.offerings.filter(item => item.game_id === props.gameId)
    : props.player.offerings
  return [...filtered].sort((a, b) => a.price - b.price)[0]
})

const heroSkill = computed(() => props.player.skills[0])
const assistSkill = computed(() => props.player.skills[1])
</script>

<template>
  <view class="card tap-scale" @click="$emit('open')">
    <view class="avatar-wrap">
      <image
        v-if="player.avatar_url"
        class="avatar"
        :src="player.avatar_url"
        mode="aspectFill"
      />
      <view v-else class="avatar fallback">{{ player.display_name.slice(0, 1) }}</view>
      <view class="presence"></view>
    </view>

    <view class="main">
      <view class="identity-row">
        <view class="identity">
          <text class="name">{{ player.display_name }}</text>
          <text class="cert">已认证</text>
        </view>
        <button v-if="offering" class="price-button">
          ¥{{ (offering.price / 100).toFixed(0) }}/局
        </button>
      </view>

      <view class="meta">
        <text>{{ player.rating > 0 ? player.rating.toFixed(1) + " 分" : "新晋大神" }}</text>
        <text class="dot">·</text>
        <text>{{ player.order_count }} 单</text>
        <template v-if="offering">
          <text class="dot">·</text>
          <text>{{ offering.game_name }}</text>
        </template>
      </view>

      <view class="tags">
        <text v-if="heroSkill" class="tag strong">{{ heroSkill.rank || heroSkill.game_name }}</text>
        <text v-if="assistSkill" class="tag">{{ assistSkill.game_name }}</text>
        <text v-if="!heroSkill && offering" class="tag strong">{{ offering.sku_name }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.card{display:flex;gap:22rpx;align-items:center;padding:24rpx;border:1rpx solid rgba(0,0,0,.09);border-radius:32rpx;background:#ffffff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.08)}.avatar-wrap{position:relative;flex:none;padding:4rpx;border:1rpx solid rgba(0,0,0,.18);border-radius:34rpx;box-shadow:0 0 24rpx rgba(0,0,0,.08)}.avatar{width:108rpx;height:108rpx;border-radius:29rpx;background:#f3f4f6}.avatar.fallback{display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,#111827,#000000);color:#fff;font-size:36rpx;font-weight:900}.presence{position:absolute;right:-2rpx;bottom:-2rpx;width:22rpx;height:22rpx;border:6rpx solid #ffffff;border-radius:50%;background:#111827;box-shadow:0 0 18rpx rgba(16,185,129,.9)}.main{flex:1;min-width:0}.identity-row{display:flex;align-items:flex-start;justify-content:space-between;gap:14rpx}.identity{display:flex;align-items:center;gap:10rpx;min-width:0}.name{overflow:hidden;color:#111827;font-size:27rpx;font-weight:900;text-overflow:ellipsis;white-space:nowrap}.cert{flex:none;padding:5rpx 9rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:999rpx;background:rgba(0,0,0,.06);color:#111827;font-size:14rpx;font-weight:850}.price-button{flex:none;height:52rpx;line-height:52rpx;margin:0;padding:0 16rpx;border-radius:999rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;font-size:18rpx;font-weight:900;box-shadow:0 10rpx 26rpx rgba(0,0,0,.10)}.meta{display:flex;align-items:center;gap:7rpx;margin-top:9rpx;color:#6b7280;font-size:19rpx}.dot{color:#4b5563}.tags{display:flex;gap:8rpx;margin-top:13rpx;overflow:hidden}.tag{max-width:210rpx;overflow:hidden;padding:7rpx 11rpx;border-radius:999rpx;background:#f3f4f6;color:#374151;font-size:16rpx;font-weight:760;text-overflow:ellipsis;white-space:nowrap}.tag.strong{border:1rpx solid rgba(0,0,0,.10);background:rgba(0,0,0,.06);color:#111827}
</style>
