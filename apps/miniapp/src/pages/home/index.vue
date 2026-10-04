<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import EmptyState from "../../components/EmptyState.vue"
import PlayerCard from "../../components/PlayerCard.vue"
import SampleJourney from "../../components/SampleJourney.vue"
import SectionHeader from "../../components/SectionHeader.vue"
import { listAnnouncements, type PublicAnnouncement } from "../../domain/announcement/api"
import { useHomeDiscovery } from "../../features/discovery/useHomeDiscovery"
import { navigation } from "../../platform/navigation"
import { scrollToSelector } from "../../platform/page"
import type { Game, PublicPlayer } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

const {
  games,
  players,
  demoMode,
  loadStatus,
  loadMessage,
  load
} = useHomeDiscovery()

const brandLogo = "/static/roots-logo.png"
const gameSubtitles = ["热血竞技", "峡谷开黑", "战术突围", "枪感陪练"]
const gameBadges = ["8k+ 在线", "6k+ 组队", "3k+ 上车", "5k+ 在线"]
const gameFallbackIcons = [
  "https://img.icons8.com/fluency/96/sword.png",
  "https://img.icons8.com/fluency/96/controller.png",
  "https://img.icons8.com/fluency/96/crosshair.png",
  "https://img.icons8.com/fluency/96/joystick.png"
]
const uiIcons = {
  shield: "https://img.icons8.com/fluency/96/security-checked.png",
  quick: "https://img.icons8.com/fluency/96/flash-on.png",
  scout: "https://img.icons8.com/fluency/96/search-more.png",
  empty: "https://img.icons8.com/fluency/96/controller.png"
}

const announcements = ref<PublicAnnouncement[]>([])
const systemAnnouncements = ref<PublicAnnouncement[]>([])
const visibleGames = computed(() => games.value.slice(0, 4))
const onlinePlayers = computed(() => players.value.slice(0, 6))
const announcementTickerItems = computed(() => {
  if (announcements.value.length <= 1) return announcements.value
  return [...announcements.value, ...announcements.value]
})

function showSystemAnnouncement(item: PublicAnnouncement) {
  const storageKey = `system_notice_seen_${item.id}`
  if (uni.getStorageSync(storageKey)) return
  uni.showModal({
    title: item.title || "系统通知",
    content: item.content || "请关注平台最新通知。",
    showCancel: false,
    confirmText: "知道了",
    success: () => {
      uni.setStorageSync(storageKey, "1")
    }
  })
}

async function loadAnnouncements() {
  try {
    const [normalRows, systemRows] = await Promise.all([
      listAnnouncements(10, "NORMAL"),
      listAnnouncements(3, "SYSTEM")
    ])
    announcements.value = normalRows
    systemAnnouncements.value = systemRows
    if (systemRows.length) showSystemAnnouncement(systemRows[0])
  } catch {
    announcements.value = []
    systemAnnouncements.value = []
  }
}

onShow(() => {
  void load()
  void loadAnnouncements()
})

function gameIconUrl(game: Game, index: number) {
  return game.icon_url || game.iconUrl || gameFallbackIcons[index % gameFallbackIcons.length]
}

function openGame(game: Game) {
  navigation.push("/pages/game/index", { id: game.id, name: game.name })
}

function openPlayer(player: PublicPlayer) {
  navigation.push("/pages/player/index", { id: player.id })
}

function openDiscover() {
  navigation.push("/pages/discover/index")
}

function openAllGames() {
  navigation.push("/pages/games/index")
}

function quickOrder() {
  if (!games.value.length) {
    showMessage("暂无可用服务")
    return
  }
  scrollToSelector("#game-list")
}
</script>

<template>
  <view class="safe-page custom-safe-page home">
    <view class="ambient one"></view>
    <view class="ambient two"></view>

    <view class="topbar">
      <view class="brand-block">
        <image class="brand-logo" :src="brandLogo" mode="aspectFit" />
        <text class="hello">Black White Companion</text>
      </view>
      <view class="shield"><image :src="uiIcons.shield" mode="aspectFit" /></view>
    </view>

    <SampleJourney
      v-if="demoMode"
      :step="1"
      title="先从用户端下第一单"
      description="选游戏和套餐，创建订单并完成模拟支付；支付后从「我的」切换到陪玩工作台。"
    />

    <view class="hero">
      <view class="hero-orbit"></view>
      <view class="hero-copy">
        <text class="hero-kicker">VIP 尊享 · 极速匹配 · 真人陪玩</text>
        <text class="hero-title">黑白尊享<br/>极速匹配终端</text>
        <text class="hero-subtitle">高段大神在线响应，娱乐开黑与上分陪练都能精准安排。</text>
      </view>
      <view class="hero-actions">
        <button class="hero-primary" @click="quickOrder">
          <view class="action-mark"><image :src="uiIcons.quick" mode="aspectFit" /></view>
          <view><b>一键安排</b><small>尊享快速匹配</small></view>
        </button>
        <button class="hero-secondary" @click="openDiscover">
          <view class="action-mark glass"><image :src="uiIcons.scout" mode="aspectFit" /></view>
          <view><b>找大神</b><small>筛选认证大神</small></view>
        </button>
      </view>
    </view>

    <view v-if="announcements.length" class="notice-strip">
      <text class="notice-label">通知</text>
      <view class="notice-viewport">
        <view
          class="notice-track"
          :class="{ rolling: announcements.length > 1 }"
          :style="{ '--notice-count': String(announcements.length) }"
        >
          <view v-for="(item, index) in announcementTickerItems" :key="item.id + '-' + index" class="notice-item">
            <text class="notice-title">{{ item.title }}</text>
            <text class="notice-content">{{ item.content }}</text>
          </view>
        </view>
      </view>
    </view>

    <view id="game-list" class="section">
      <SectionHeader title="选游戏" description="先选游戏，再选择服务套餐" action="查看全部 ›" @action="openAllGames" />
      <view v-if="loadStatus === 'loading'" class="game-grid">
        <view v-for="n in 4" :key="n" class="game-skeleton skeleton"></view>
      </view>
      <EmptyState
        v-else-if="loadStatus === 'error'"
        title="服务暂时没加载出来"
        :description="loadMessage"
        action="重新加载"
        symbol="↻"
        @action="load"
      />
      <view v-else class="game-grid">
        <view
          v-for="(game,index) in visibleGames"
          :key="game.id"
          class="game-card tap-scale"
          @click="openGame(game)"
        >
          <view class="game-art" :class="'tone-' + (index % 4)">
            <image :src="gameIconUrl(game, index)" mode="aspectFill" />
          </view>
          <view class="game-main">
            <text class="game-name">{{ game.name }}</text>
            <text class="game-subtitle">{{ gameSubtitles[index % gameSubtitles.length] }}</text>
          </view>
          <text class="game-badge">{{ gameBadges[index % gameBadges.length] }}</text>
        </view>
      </view>
    </view>

    <view class="guarantee">
      <view><text>平台担保</text></view>
      <view><text>完成后结算</text></view>
      <view><text>售后可追踪</text></view>
    </view>

    <view class="section">
      <SectionHeader
        title="正在接单"
        description="在线陪玩师 · 快速响应"
        action="查看全部 ›"
        @action="openDiscover"
      />
      <view v-if="loadStatus === 'loading'" class="player-list">
        <view v-for="n in 3" :key="n" class="player-skeleton skeleton"></view>
      </view>
      <view v-else-if="loadStatus !== 'error' && !onlinePlayers.length" class="empty-online">
        <view class="empty-illust">
          <image class="empty-core" :src="uiIcons.empty" mode="aspectFit" />
        </view>
        <text class="empty-title">暂无在线陪玩</text>
        <text class="empty-desc">可以先下单，系统会在优质大神池里自动推送。</text>
      </view>
      <view v-else class="player-list">
        <PlayerCard
          v-for="player in onlinePlayers"
          :key="player.id"
          :player="player"
          @open="openPlayer(player)"
        />
      </view>
    </view>
  </view>
</template>

<style scoped>
.home{position:relative;min-height:100vh;padding-top:24rpx;background:#f7f7f8;overflow:hidden;color:#111827}.ambient{position:absolute;pointer-events:none;border-radius:999rpx;filter:blur(22rpx)}.ambient.one{width:520rpx;height:260rpx;left:-150rpx;top:-120rpx;background:rgba(0,0,0,.08)}.ambient.two{width:360rpx;height:220rpx;right:-150rpx;top:130rpx;background:rgba(0,0,0,.05)}.home :deep(.section-head .title){color:#111827}.home :deep(.section-head .description){color:#6b7280}.home :deep(.section-head .action){color:#111827}.topbar{position:relative;z-index:1;display:flex;align-items:center;justify-content:space-between;margin-bottom:24rpx}.brand-block{min-width:0}.brand-logo{display:block;width:278rpx;height:72rpx;margin-bottom:7rpx}.hello{display:block;color:#a3a3a3;font-size:19rpx;font-weight:650}.shield{width:64rpx;height:64rpx;display:flex;align-items:center;justify-content:center;border:1rpx solid rgba(0,0,0,.12);border-radius:22rpx;background:#ffffff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.38)}.shield image{width:38rpx;height:38rpx}.hero{position:relative;z-index:1;overflow:hidden;padding:44rpx 34rpx 32rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:38rpx;background:linear-gradient(135deg,#111827 0%,#ffffff 100%);color:#fff;box-shadow:0 24rpx 72rpx rgba(0,0,0,.5)}.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 85% 8%,rgba(0,0,0,.12),transparent 30%),linear-gradient(115deg,transparent,rgba(0,0,0,.04),transparent)}.hero-orbit{position:absolute;right:-96rpx;top:-76rpx;width:280rpx;height:280rpx;border:2rpx solid rgba(0,0,0,.08);border-radius:50%}.hero-copy,.hero-actions{position:relative;z-index:1}.hero-kicker{display:block;color:#111827;font-size:18rpx;font-weight:800;letter-spacing:2rpx}.hero-title{display:block;margin-top:16rpx;font-size:47rpx;font-weight:950;line-height:1.18}.hero-subtitle{display:block;width:520rpx;max-width:100%;margin-top:15rpx;color:#4b5563;font-size:20rpx;line-height:1.55}.hero-actions{display:flex;gap:14rpx;margin-top:34rpx}.hero-actions button{flex:1;min-height:94rpx;margin:0;padding:17rpx 18rpx;display:flex;align-items:center;gap:12rpx;border-radius:25rpx;text-align:left}.hero-actions b,.hero-actions small{display:block;line-height:1.2}.hero-actions b{font-size:22rpx}.hero-actions small{margin-top:6rpx;font-size:16rpx;font-weight:500}.hero-primary{background:linear-gradient(135deg,#111827,#000000);color:#fff;box-shadow:0 14rpx 34rpx rgba(0,0,0,.12)}.hero-secondary{border:1rpx solid rgba(0,0,0,.10);background:rgba(31,34,46,.72);color:#fff;backdrop-filter:blur(18rpx)}.action-mark{width:43rpx;height:43rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:14rpx;background:rgba(11,12,16,.26)}.action-mark image{width:28rpx;height:28rpx}.action-mark.glass{background:rgba(0,0,0,.08)}.notice-strip{position:relative;z-index:1;display:flex;align-items:center;gap:16rpx;margin-top:20rpx;padding:16rpx 20rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:24rpx;background:#ffffff;box-shadow:0 12rpx 32rpx rgba(0,0,0,.10)}.notice-label{flex:none;height:34rpx;padding:0 12rpx;border-radius:999rpx;background:#111827;color:#fff;font-size:17rpx;font-weight:800;line-height:34rpx}.notice-viewport{height:58rpx;min-width:0;flex:1;overflow:hidden}.notice-track{height:58rpx;display:inline-flex;align-items:center;gap:48rpx;white-space:nowrap}.notice-track.rolling{animation:noticeRoll calc(var(--notice-count) * 4.2s) linear infinite}.notice-item{height:58rpx;display:inline-flex;align-items:center;gap:12rpx;flex:none}.notice-title,.notice-content{display:inline-block;white-space:nowrap}.notice-title{color:#111827;font-size:21rpx;font-weight:850}.notice-content{color:#6b7280;font-size:17rpx;line-height:1.25}@keyframes noticeRoll{0%{transform:translateX(-50%)}100%{transform:translateX(0)}}.section{position:relative;z-index:1;margin-top:40rpx}.game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16rpx}.game-card{position:relative;min-height:166rpx;display:grid;grid-template-columns:86rpx minmax(0,1fr);align-items:center;gap:14rpx;padding:20rpx 16rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:28rpx;background:#ffffff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.08)}.game-art{width:86rpx;height:86rpx;flex:none;display:flex;align-items:center;justify-content:center;overflow:hidden;border:1rpx solid rgba(0,0,0,.10);border-radius:24rpx;color:#fff;font-size:34rpx;font-weight:900}.game-art image{width:100%;height:100%;display:block}.tone-0{background:linear-gradient(145deg,#111827,#000000)}.tone-1{background:linear-gradient(145deg,#111827,#111827)}.tone-2{background:linear-gradient(145deg,#111827,#111827)}.tone-3{background:linear-gradient(145deg,#111827,#111827)}.game-main{min-width:0;padding-top:30rpx}.game-name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#111827;font-size:23rpx;font-weight:900}.game-subtitle{display:block;margin-top:7rpx;color:#6b7280;font-size:18rpx}.game-badge{position:absolute;right:12rpx;top:12rpx;padding:6rpx 10rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:999rpx;background:rgba(0,0,0,.06);color:#111827;font-size:14rpx;font-weight:850}.game-skeleton{height:154rpx;border-radius:30rpx;background:#ffffff}.guarantee{position:relative;z-index:1;display:flex;gap:12rpx;margin-top:22rpx}.guarantee view{flex:1;display:flex;justify-content:center;padding:14rpx 10rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:999rpx;background:#ffffff;box-shadow:0 10rpx 30rpx rgba(0,0,0,.2)}.guarantee text{color:#111827;font-size:17rpx;font-weight:760;white-space:nowrap}.player-list{display:flex;flex-direction:column;gap:15rpx}.player-skeleton{height:168rpx;border-radius:32rpx;background:#ffffff}.empty-online{padding:46rpx 28rpx;border:1rpx solid rgba(0,0,0,.09);border-radius:34rpx;background:#ffffff;text-align:center;box-shadow:0 18rpx 46rpx rgba(0,0,0,.28)}.empty-illust{width:150rpx;height:112rpx;margin:0 auto 18rpx;display:flex;align-items:center;justify-content:center;border-radius:34rpx;background:linear-gradient(145deg,#f3f4f6,#111827)}.empty-core{width:84rpx;height:58rpx;padding:10rpx;border-radius:20rpx;background:linear-gradient(135deg,#111827,#000000)}.empty-title{display:block;color:#111827;font-size:25rpx;font-weight:900}.empty-desc{display:block;margin-top:9rpx;color:#6b7280;font-size:19rpx;line-height:1.5}
</style>
