<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import { listGames } from "../../domain/catalog/api"
import { navigation } from "../../platform/navigation"
import type { Game } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

const games = ref<Game[]>([])
const loading = ref(true)
const error = ref("")

const fallbackIcons = [
  "https://img.icons8.com/fluency/96/sword.png",
  "https://img.icons8.com/fluency/96/controller.png",
  "https://img.icons8.com/fluency/96/crosshair.png",
  "https://img.icons8.com/fluency/96/joystick.png"
]
const subtitles = ["热血竞技", "峡谷开黑", "战术突围", "枪感陪练"]

function gameIconUrl(game: Game, index: number) {
  return game.icon_url || game.iconUrl || fallbackIcons[index % fallbackIcons.length]
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    games.value = await listGames()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "游戏列表加载失败"
    showMessage(error.value)
  } finally {
    loading.value = false
  }
}

function openGame(game: Game) {
  navigation.push("/pages/game/index", { id: game.id, name: game.name })
}

onShow(() => {
  void load()
})
</script>

<template>
  <view class="safe-page games-page">
    <view class="heading">
      <text class="eyebrow">GAME CATALOG</text>
      <text class="title">全部游戏</text>
      <text class="subtitle">选择一个游戏后，再进入服务套餐下单。</text>
    </view>

    <view v-if="loading" class="game-grid">
      <view v-for="n in 8" :key="n" class="game-skeleton skeleton"></view>
    </view>

    <EmptyState
      v-else-if="error"
      title="游戏列表加载失败"
      :description="error"
      action="重新加载"
      symbol="↻"
      @action="load"
    />

    <EmptyState
      v-else-if="!games.length"
      title="暂无可选游戏"
      description="请在后台服务配置中启用游戏。"
      symbol="·"
    />

    <view v-else class="game-grid">
      <view
        v-for="(game, index) in games"
        :key="game.id"
        class="game-card tap-scale"
        @click="openGame(game)"
      >
        <view class="game-art">
          <image :src="gameIconUrl(game, index)" mode="aspectFill" />
        </view>
        <view class="game-main">
          <text class="game-name">{{ game.name }}</text>
          <text class="game-subtitle">{{ subtitles[index % subtitles.length] }}</text>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.games-page{min-height:100vh;padding-top:24rpx;background:#f7f7f8;color:#111827}.heading{padding:8rpx 3rpx 28rpx}.eyebrow{display:block;color:#111827;font-size:16rpx;font-weight:900;letter-spacing:3rpx}.title{display:block;margin-top:10rpx;color:#111827;font-size:40rpx;font-weight:900}.subtitle{display:block;margin-top:8rpx;color:#6b7280;font-size:20rpx;line-height:1.5}.game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18rpx}.game-card{position:relative;min-height:172rpx;display:grid;grid-template-columns:92rpx minmax(0,1fr) 24rpx;align-items:center;gap:16rpx;padding:22rpx 18rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:30rpx;background:#ffffff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.08)}.game-art{width:92rpx;height:92rpx;overflow:hidden;border:1rpx solid rgba(0,0,0,.10);border-radius:24rpx;background:#111827}.game-art image{width:100%;height:100%;display:block}.game-main{min-width:0}.game-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#111827;font-size:24rpx;font-weight:900}.game-subtitle{display:block;margin-top:9rpx;color:#6b7280;font-size:18rpx}.arrow{color:#6b7280;font-size:34rpx}.game-skeleton{height:172rpx;border-radius:30rpx;background:#ffffff}
</style>
