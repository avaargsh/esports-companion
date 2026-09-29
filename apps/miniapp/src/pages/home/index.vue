<script setup lang="ts">
import { onMounted, ref } from "vue"

import { request } from "../../api/client"
import type { Game } from "../../types/domain"

const games = ref<Game[]>([])
const loading = ref(true)
const failed = ref(false)

async function loadGames() {
  loading.value = true
  failed.value = false
  try {
    games.value = await request<Game[]>("/games")
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => { void loadGames() })

function openGame(game: Game) {
  uni.navigateTo({
    url: `/pages/game/index?id=${game.id}&name=${encodeURIComponent(game.name)}`
  })
}

function openPlayerWorkspace() {
  uni.navigateTo({ url: "/pages-player/workbench/index" })
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <view>
        <text class="eyebrow">ESPORTS COMPANION</text>
        <view class="title">今晚一起上分</view>
        <view class="subtitle">选游戏 · 选服务 · 即时匹配</view>
      </view>
      <button class="workspace-button" @click="openPlayerWorkspace">我是陪玩</button>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">热门游戏</text>
        <text class="section-link">按游戏下单</text>
      </view>

      <view v-if="loading" class="empty-card">正在加载服务…</view>
      <view v-else-if="failed" class="empty-card" @click="loadGames">加载失败，点此重试</view>
      <view v-else class="game-grid">
        <view v-for="game in games" :key="game.id" class="game-card" @click="openGame(game)">
          <view class="game-icon">{{ game.name.slice(0, 1) }}</view>
          <text class="game-name">{{ game.name }}</text>
        </view>
      </view>
    </view>

    <view class="trust-strip">
      <view><text class="dot">1</text><text>平台订单</text></view>
      <view><text class="dot">2</text><text>实时匹配</text></view>
      <view><text class="dot">3</text><text>完成后结算</text></view>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">推荐大神</text>
        <text class="section-link">榜单能力待接入</text>
      </view>
      <view class="provider-card">
        <view class="avatar">P</view>
        <view class="provider-main">
          <view class="provider-title">
            <text class="provider-name">Demo Player</text>
            <text class="online">可接单</text>
          </view>
          <text class="provider-desc">当前为产品占位卡，后续接评分与服务档案</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.hero { min-height: 300rpx; padding: 42rpx; border-radius: 36rpx; background: linear-gradient(135deg,#6252df,#8877f4); color: #fff; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 24rpx 70rpx rgba(108,92,231,.22); }
.eyebrow { font-size: 20rpx; opacity: .72; letter-spacing: 3rpx; }
.title { margin-top: 18rpx; font-size: 48rpx; font-weight: 800; }
.subtitle { margin-top: 12rpx; font-size: 25rpx; opacity: .9; }
.workspace-button { margin: 34rpx 0 0; width: 210rpx; height: 70rpx; line-height: 70rpx; border-radius: 23rpx; background: rgba(255,255,255,.17); color: #fff; font-size: 24rpx; }
.section { margin-top: 40rpx; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 22rpx; }
.section-title { font-size: 32rpx; font-weight: 700; }
.section-link { color: #92929d; font-size: 21rpx; }
.game-grid { display: flex; flex-wrap: wrap; gap: 18rpx; }
.game-card { width: calc(25% - 14rpx); padding: 24rpx 8rpx; border-radius: 28rpx; background: #fff; text-align: center; box-shadow: 0 10rpx 32rpx rgba(25,20,60,.04); box-sizing: border-box; }
.game-icon { width: 76rpx; height: 76rpx; margin: 0 auto 14rpx; border-radius: 24rpx; display: flex; align-items: center; justify-content: center; background: #f0edff; color: #6c5ce7; font-size: 30rpx; font-weight: 800; }
.game-name { font-size: 22rpx; }
.empty-card { padding: 44rpx; border-radius: 28rpx; background: #fff; color: #92929d; text-align: center; }
.trust-strip { margin-top: 28rpx; padding: 24rpx; display: flex; justify-content: space-between; border-radius: 28rpx; background: #fff; }
.trust-strip view { display: flex; align-items: center; gap: 8rpx; color: #686872; font-size: 20rpx; }
.dot { width: 34rpx; height: 34rpx; border-radius: 50%; background: #f0edff; color: #6c5ce7; display: inline-flex; align-items: center; justify-content: center; font-size: 18rpx; font-weight: 700; }
.provider-card { display: flex; align-items: center; gap: 22rpx; padding: 28rpx; border-radius: 32rpx; background: #fff; }
.avatar { width: 96rpx; height: 96rpx; border-radius: 30rpx; background: #17171f; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 36rpx; font-weight: 800; }
.provider-main { flex: 1; min-width: 0; }
.provider-title { display: flex; align-items: center; gap: 12rpx; }
.provider-name { font-size: 29rpx; font-weight: 700; }
.online { padding: 6rpx 12rpx; border-radius: 999rpx; background: #eafbf2; color: #22a665; font-size: 18rpx; }
.provider-desc { display: block; margin-top: 10rpx; color: #92929d; font-size: 21rpx; }
</style>
