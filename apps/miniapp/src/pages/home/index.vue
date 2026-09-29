<script setup lang="ts">
import { onMounted, ref } from "vue"

import { request } from "../../api/client"
import type { Game } from "../../types/domain"

const games = ref<Game[]>([])
const loading = ref(true)

async function loadGames() {
  loading.value = true
  try {
    games.value = await request<Game[]>("/games")
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "加载失败",
      icon: "none"
    })
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

function openOrders() {
  uni.switchTab({ url: "/pages/orders/index" })
}
</script>

<template>
  <view class="page">
    <view class="topbar">
      <view>
        <text class="hello">晚上好</text>
        <view class="headline">找个靠谱队友，一起玩</view>
      </view>
      <view class="avatar" @click="openOrders">B</view>
    </view>

    <view class="hero">
      <view class="hero-copy">
        <view class="hero-badge">⚡ 即时匹配</view>
        <view class="hero-title">今晚一起上分</view>
        <view class="hero-subtitle">实名认证 · 平台担保 · 服务后结算</view>
      </view>
      <view class="hero-orb hero-orb-a"></view>
      <view class="hero-orb hero-orb-b"></view>
      <button class="workspace-button" @click="openPlayerWorkspace">切换陪玩师端 <text>→</text></button>
    </view>

    <view class="trust-row">
      <view><text class="trust-icon">✓</text><text>担保交易</text></view>
      <view><text class="trust-icon">✓</text><text>真人认证</text></view>
      <view><text class="trust-icon">✓</text><text>售后保障</text></view>
    </view>

    <view class="section">
      <view class="section-head">
        <view><text class="section-title">热门游戏</text><text class="section-subtitle">选游戏，再选服务规格</text></view>
        <text class="section-link">全部</text>
      </view>

      <view v-if="loading" class="empty-card">正在加载游戏…</view>
      <view v-else class="game-grid">
        <view v-for="(game,index) in games" :key="game.id" class="game-card" @click="openGame(game)">
          <view class="game-icon" :class="`tone-${index % 4}`">{{ game.name.slice(0,1) }}</view>
          <text class="game-name">{{ game.name }}</text>
          <text class="game-action">立即下单</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <view><text class="section-title">本周人气陪玩</text><text class="section-subtitle">高响应、高好评优先展示</text></view>
        <text class="section-link">换一批</text>
      </view>

      <view class="provider-card">
        <view class="provider-avatar">鹿<text class="online-dot"></text></view>
        <view class="provider-main">
          <view class="provider-title"><text class="provider-name">小鹿</text><text class="level">LV.8</text></view>
          <text class="provider-desc">王者荣耀 · 国服辅助 · 开麦友好</text>
          <view class="provider-meta"><text>★ 4.9</text><text>268 单</text><text>98% 好评</text></view>
        </view>
        <view class="price"><text class="price-value">¥30</text><text class="price-unit">起</text></view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding:24rpx 28rpx 48rpx; }
.topbar { display:flex; align-items:center; justify-content:space-between; padding:16rpx 2rpx 26rpx; }
.hello { color:#94949f; font-size:21rpx; }
.headline { margin-top:6rpx; color:#17171e; font-size:34rpx; font-weight:800; letter-spacing:-1rpx; }
.avatar { width:70rpx; height:70rpx; display:flex; align-items:center; justify-content:center; border-radius:24rpx; background:#17171f; color:#fff; font-size:26rpx; font-weight:800; }
.hero { position:relative; min-height:330rpx; overflow:hidden; padding:38rpx; border-radius:38rpx; background:linear-gradient(135deg,#5e4bd8 0%,#7b68ee 58%,#9a86ff 100%); color:white; box-shadow:0 20rpx 56rpx rgba(92,75,216,.22); }
.hero-copy { position:relative; z-index:2; }
.hero-badge { display:inline-flex; padding:8rpx 14rpx; border-radius:999rpx; background:rgba(255,255,255,.15); font-size:19rpx; }
.hero-title { margin-top:24rpx; font-size:48rpx; font-weight:850; letter-spacing:-2rpx; }
.hero-subtitle { margin-top:12rpx; font-size:22rpx; opacity:.84; }
.hero-orb { position:absolute; border-radius:50%; background:rgba(255,255,255,.11); }
.hero-orb-a { width:240rpx; height:240rpx; right:-70rpx; top:-50rpx; }
.hero-orb-b { width:120rpx; height:120rpx; right:116rpx; bottom:-46rpx; }
.workspace-button { position:absolute; z-index:2; left:38rpx; bottom:32rpx; margin:0; height:64rpx; line-height:64rpx; padding:0 22rpx; border-radius:20rpx; background:rgba(17,17,25,.22); color:#fff; font-size:21rpx; }
.trust-row { display:flex; justify-content:space-around; margin-top:18rpx; padding:24rpx 14rpx; border-radius:28rpx; background:#fff; color:#6f6f79; font-size:20rpx; box-shadow:0 10rpx 36rpx rgba(25,20,60,.045); }
.trust-row view { display:flex; align-items:center; gap:7rpx; }
.trust-icon { width:28rpx; height:28rpx; display:inline-flex; align-items:center; justify-content:center; border-radius:50%; background:#ecfbf3; color:#1da45d; font-size:16rpx; font-weight:800; }
.section { margin-top:38rpx; }
.section-head { display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:20rpx; }
.section-title { display:block; color:#17171e; font-size:31rpx; font-weight:800; }
.section-subtitle { display:block; margin-top:6rpx; color:#a0a0aa; font-size:19rpx; }
.section-link { color:#6c5ce7; font-size:20rpx; }
.game-grid { display:flex; flex-wrap:wrap; gap:16rpx; }
.game-card { width:calc(25% - 12rpx); padding:22rpx 8rpx 18rpx; border-radius:28rpx; background:#fff; text-align:center; box-shadow:0 10rpx 30rpx rgba(25,20,60,.04); }
.game-icon { width:76rpx; height:76rpx; margin:0 auto 13rpx; border-radius:24rpx; display:flex; align-items:center; justify-content:center; font-size:29rpx; font-weight:850; }
.tone-0 { background:#f0edff; color:#6c5ce7; }
.tone-1 { background:#eaf9ff; color:#2487b8; }
.tone-2 { background:#fff4e6; color:#d47a12; }
.tone-3 { background:#eafbf2; color:#24985d; }
.game-name { display:block; overflow:hidden; color:#25252d; font-size:21rpx; font-weight:650; white-space:nowrap; text-overflow:ellipsis; }
.game-action { display:block; margin-top:5rpx; color:#aaaab3; font-size:17rpx; }
.provider-card { display:flex; align-items:center; gap:20rpx; padding:28rpx; border-radius:34rpx; background:#fff; box-shadow:0 14rpx 42rpx rgba(25,20,60,.06); }
.provider-avatar { position:relative; width:104rpx; height:104rpx; flex:none; border-radius:32rpx; background:linear-gradient(145deg,#eeeaff,#d8d1ff); color:#624fdc; display:flex; align-items:center; justify-content:center; font-size:38rpx; font-weight:850; }
.online-dot { position:absolute; right:-2rpx; bottom:8rpx; width:20rpx; height:20rpx; border:4rpx solid #fff; border-radius:50%; background:#24c875; }
.provider-main { flex:1; min-width:0; }
.provider-title { display:flex; align-items:center; gap:10rpx; }
.provider-name { font-size:28rpx; font-weight:780; }
.level { padding:4rpx 9rpx; border-radius:10rpx; background:#17171f; color:#fff; font-size:16rpx; }
.provider-desc { display:block; margin-top:9rpx; overflow:hidden; color:#686872; font-size:21rpx; white-space:nowrap; text-overflow:ellipsis; }
.provider-meta { display:flex; flex-wrap:wrap; gap:12rpx; margin-top:12rpx; color:#9b9ba5; font-size:18rpx; }
.price { flex:none; text-align:right; }
.price-value { display:block; color:#6c5ce7; font-size:33rpx; font-weight:850; }
.price-unit { color:#a0a0aa; font-size:18rpx; }
.empty-card { padding:42rpx; border-radius:28rpx; background:#fff; color:#92929d; text-align:center; font-size:22rpx; }
</style>
