<script setup lang="ts">
import { onMounted, ref } from "vue"

import { request } from "../../api/client"
import type { Game, PublicPlayer } from "../../types/domain"

const games = ref<Game[]>([])
const players = ref<PublicPlayer[]>([])
const loading = ref(true)
const failed = ref(false)

async function loadHome() {
  loading.value = true
  failed.value = false
  try {
    const [gameItems, playerItems] = await Promise.all([
      request<Game[]>("/games"),
      request<PublicPlayer[]>("/players?limit=4")
    ])
    games.value = gameItems
    players.value = playerItems
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => { void loadHome() })

function openGame(game: Game) {
  uni.navigateTo({
    url: `/pages/game/index?id=${game.id}&name=${encodeURIComponent(game.name)}`
  })
}

function openPlayer(player: PublicPlayer) {
  uni.navigateTo({ url: `/pages/player/index?id=${player.id}` })
}

function openDiscover() {
  uni.navigateTo({ url: "/pages/discover/index" })
}

function quickOrder() {
  if (!games.value.length) {
    uni.showToast({ title: "暂无可用服务", icon: "none" })
    return
  }
  uni.pageScrollTo({ selector: "#game-list", duration: 250 })
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="eyebrow">ESPORTS COMPANION</text>
      <view class="title">找陪玩，直接下单</view>
      <view class="subtitle">按服务快速匹配，或指定喜欢的大神。</view>

      <view class="hero-actions">
        <button class="primary-action" @click="quickOrder">一键安排</button>
        <button class="secondary-action" @click="openDiscover">找大神</button>
      </view>
    </view>

    <view id="game-list" class="section">
      <view class="section-head">
        <view>
          <text class="section-title">选游戏下单</text>
          <text class="section-desc">选择套餐后进入平台匹配</text>
        </view>
      </view>

      <view v-if="loading" class="empty-card">正在加载服务…</view>
      <view v-else-if="failed" class="empty-card" @click="loadHome">加载失败，点此重试</view>
      <view v-else class="game-grid">
        <view v-for="game in games" :key="game.id" class="game-card" @click="openGame(game)">
          <view class="game-icon">{{ game.name.slice(0, 1) }}</view>
          <text class="game-name">{{ game.name }}</text>
        </view>
      </view>
    </view>

    <view class="trust-strip">
      <text>平台订单</text>
      <text>完成后结算</text>
      <text>有问题可售后</text>
    </view>

    <view class="section">
      <view class="section-head">
        <view>
          <text class="section-title">想指定陪玩？</text>
          <text class="section-desc">看技能、评分和价格再选择</text>
        </view>
        <text class="section-link" @click="openDiscover">找大神 ›</text>
      </view>

      <view v-if="!loading && players.length === 0" class="empty-card">暂无可接单大神</view>
      <view
        v-for="player in players"
        :key="player.id"
        class="provider-card"
        @click="openPlayer(player)"
      >
        <image v-if="player.avatar_url" class="avatar-image" :src="player.avatar_url" mode="aspectFill" />
        <view v-else class="avatar">{{ player.display_name.slice(0, 1) }}</view>
        <view class="provider-main">
          <view class="provider-title">
            <text class="provider-name">{{ player.display_name }}</text>
            <text class="online">可接单</text>
          </view>
          <text class="provider-desc">
            {{ player.rating > 0 ? player.rating.toFixed(1) + "分" : "新大神" }}
            · {{ player.order_count }} 单
            · {{ player.offerings[0]?.game_name }}
          </text>
          <text v-if="player.offerings[0]" class="provider-price">
            ¥{{ (player.offerings[0].price / 100).toFixed(2) }} 起
          </text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.hero { min-height: 300rpx; padding: 42rpx; border-radius: 36rpx; background: linear-gradient(135deg,#6252df,#8877f4); color: #fff; box-shadow: 0 24rpx 70rpx rgba(108,92,231,.22); }
.eyebrow { font-size: 20rpx; opacity: .72; letter-spacing: 3rpx; }
.title { margin-top: 18rpx; font-size: 46rpx; font-weight: 800; }
.subtitle { margin-top: 12rpx; font-size: 24rpx; opacity: .9; }
.hero-actions { display:flex; gap:14rpx; margin-top:42rpx; }
.hero-actions button { flex:1; margin:0; height:76rpx; line-height:76rpx; border-radius:24rpx; font-size:24rpx; font-weight:750; }
.primary-action { background:#fff; color:#5f50d7; }
.secondary-action { background:rgba(255,255,255,.17); color:#fff; }
.section { margin-top: 40rpx; }
.section-head { display:flex; justify-content:space-between; align-items:flex-end; gap:20rpx; margin-bottom:22rpx; }
.section-title,.section-desc { display:block; }
.section-title { font-size: 31rpx; font-weight: 750; }
.section-desc { margin-top:7rpx; color:#92929d; font-size:19rpx; }
.section-link { color: #6c5ce7; font-size: 21rpx; font-weight:700; }
.game-grid { display: flex; flex-wrap: wrap; gap: 18rpx; }
.game-card { width: calc(25% - 14rpx); padding: 24rpx 8rpx; border-radius: 28rpx; background: #fff; text-align: center; box-shadow: 0 10rpx 32rpx rgba(25,20,60,.04); box-sizing: border-box; }
.game-icon { width: 76rpx; height: 76rpx; margin: 0 auto 14rpx; border-radius: 24rpx; display: flex; align-items: center; justify-content: center; background: #f0edff; color: #6c5ce7; font-size: 30rpx; font-weight: 800; }
.game-name { font-size: 22rpx; }
.empty-card { padding: 44rpx; border-radius: 28rpx; background: #fff; color: #92929d; text-align: center; }
.trust-strip { margin-top:28rpx; display:flex; justify-content:space-between; gap:10rpx; padding:22rpx 24rpx; border-radius:26rpx; background:#fff; color:#777783; font-size:19rpx; }
.provider-card { display: flex; align-items: center; gap: 22rpx; padding: 28rpx; margin-bottom: 16rpx; border-radius: 32rpx; background: #fff; }
.avatar-image { width: 96rpx; height: 96rpx; border-radius: 30rpx; }
.avatar { width: 96rpx; height: 96rpx; border-radius: 30rpx; background: #17171f; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 36rpx; font-weight: 800; }
.provider-main { flex: 1; min-width: 0; }
.provider-title { display: flex; align-items: center; gap: 12rpx; }
.provider-name { font-size: 29rpx; font-weight: 700; }
.online { padding: 6rpx 12rpx; border-radius: 999rpx; background: #eafbf2; color: #22a665; font-size: 18rpx; }
.provider-desc { display: block; margin-top: 10rpx; color: #92929d; font-size: 21rpx; }
.provider-price { display: block; margin-top: 8rpx; color: #6c5ce7; font-size: 23rpx; font-weight: 700; }
</style>
