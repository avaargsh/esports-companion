<script setup lang="ts">
import { computed } from "vue"
import type { PublicPlayer } from "../types/domain"
import UiBadge from "./ui/UiBadge.vue"

const props = defineProps<{ player: PublicPlayer; gameId?: string }>()
defineEmits<{ open: [] }>()

const offering = computed(() => {
  const filtered = props.gameId
    ? props.player.offerings.filter(item => item.game_id === props.gameId)
    : props.player.offerings
  return [...filtered].sort((a, b) => a.price - b.price)[0]
})
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
      <view class="top">
        <view class="identity">
          <text class="name">{{ player.display_name }}</text>
          <UiBadge tone="brand">已认证</UiBadge>
        </view>
        <view v-if="offering" class="price">
          <text class="currency">¥</text>{{ (offering.price / 100).toFixed(0) }}
          <text class="unit">起</text>
        </view>
      </view>

      <view class="meta">
        <text>{{ player.rating > 0 ? player.rating.toFixed(1) + " ★" : "新大神" }}</text>
        <text class="dot">·</text>
        <text>{{ player.order_count }} 单</text>
        <template v-if="offering">
          <text class="dot">·</text>
          <text>{{ offering.game_name }}</text>
        </template>
      </view>

      <view class="tags">
        <UiBadge
          v-for="skill in player.skills.slice(0, 2)"
          :key="skill.id"
          tone="neutral"
        >
          {{ skill.game_name }} {{ skill.rank }}
        </UiBadge>
        <UiBadge v-if="!player.skills.length && offering" tone="neutral">
          {{ offering.sku_name }}
        </UiBadge>
      </view>
    </view>
  </view>
</template>

<style scoped>
.card {
  display: flex;
  gap: 22rpx;
  align-items: center;
  padding: 24rpx;
  border: 1rpx solid rgba(20, 20, 30, 0.035);
  border-radius: 30rpx;
  background: #fff;
  box-shadow: var(--shadow-card);
}

.avatar-wrap {
  position: relative;
  flex: none;
}

.avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: 30rpx;
  background: #eeeef4;
}

.avatar.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #211f2d, #6757e6);
  color: #fff;
  font-size: 35rpx;
  font-weight: 850;
}

.presence {
  position: absolute;
  right: -2rpx;
  bottom: -2rpx;
  width: 22rpx;
  height: 22rpx;
  border: 5rpx solid #fff;
  border-radius: 50%;
  background: #2dbb77;
}

.main {
  flex: 1;
  min-width: 0;
}

.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
}

.identity {
  display: flex;
  align-items: center;
  gap: 10rpx;
  min-width: 0;
}

.name {
  overflow: hidden;
  color: var(--ink);
  font-size: 28rpx;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.price {
  flex: none;
  color: var(--ink);
  font-size: 31rpx;
  font-weight: 850;
  letter-spacing: -1rpx;
}

.currency,
.unit {
  font-size: 17rpx;
  font-weight: 700;
}

.unit {
  margin-left: 3rpx;
  color: var(--muted);
}

.meta {
  display: flex;
  align-items: center;
  gap: 7rpx;
  margin-top: 9rpx;
  color: var(--muted);
  font-size: 19rpx;
}

.dot {
  color: #c4c4cc;
}

.tags {
  display: flex;
  gap: 8rpx;
  margin-top: 13rpx;
  overflow: hidden;
}
</style>
