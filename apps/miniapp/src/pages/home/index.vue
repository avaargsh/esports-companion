<script setup lang="ts">
import { onMounted, ref } from "vue"
import { request } from "../../api/client"
import EmptyState from "../../components/EmptyState.vue"
import PlayerCard from "../../components/PlayerCard.vue"
import SectionHeader from "../../components/SectionHeader.vue"
import type { Game, PublicPlayer } from "../../types/domain"
import { showMessage } from "../../ui/feedback"

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
  uni.navigateTo({ url: `/pages/game/index?id=${game.id}&name=${encodeURIComponent(game.name)}` })
}
function openPlayer(player: PublicPlayer) {
  uni.navigateTo({ url: `/pages/player/index?id=${player.id}` })
}
function openDiscover() {
  uni.navigateTo({ url: "/pages/discover/index" })
}
function quickOrder() {
  if (!games.value.length) {
    showMessage("暂无可用服务")
    return
  }
  uni.pageScrollTo({ selector: "#game-list", duration: 260 })
}
</script>

<template>
  <view class="safe-page custom-safe-page home">
    <view class="topbar">
      <view>
        <text class="hello">今天想玩点什么？</text>
        <text class="brand">PLAYMATE</text>
      </view>
      <view class="shield">保</view>
    </view>

    <view class="hero">
      <view class="hero-glow one"></view>
      <view class="hero-glow two"></view>
      <view class="hero-copy">
        <text class="hero-kicker">极速匹配 · 平台担保</text>
        <text class="hero-title">找到合拍的队友，<br/>马上开一局。</text>
        <text class="hero-subtitle">不想挑人就一键安排，想指定就看大神。</text>
      </view>
      <view class="hero-actions">
        <button class="hero-primary" @click="quickOrder">
          <text class="action-icon">⚡</text>
          <view><b>一键安排</b><small>按服务快速匹配</small></view>
        </button>
        <button class="hero-secondary" @click="openDiscover">
          <text class="action-icon">⌕</text>
          <view><b>找大神</b><small>看技能和评价</small></view>
        </button>
      </view>
    </view>

    <view id="game-list" class="section">
      <SectionHeader title="选游戏" description="先选游戏，再选你需要的服务" />
      <view v-if="loading" class="game-grid">
        <view v-for="n in 4" :key="n" class="game-skeleton skeleton"></view>
      </view>
      <EmptyState
        v-else-if="failed"
        title="服务暂时没加载出来"
        description="网络恢复后再试一次"
        action="重新加载"
        symbol="↻"
        @action="loadHome"
      />
      <view v-else class="game-grid">
        <view
          v-for="(game,index) in games"
          :key="game.id"
          class="game-card tap-scale"
          @click="openGame(game)"
        >
          <view class="game-icon" :class="'tone-' + (index % 4)">
            {{ game.name.slice(0, 1) }}
          </view>
          <text class="game-name">{{ game.name }}</text>
          <text class="game-more">选服务 ›</text>
        </view>
      </view>
    </view>

    <view class="guarantee">
      <view><b>平台担保</b><text>订单全程留痕</text></view>
      <view class="divider"></view>
      <view><b>完成后结算</b><text>服务完成再放款</text></view>
      <view class="divider"></view>
      <view><b>售后可追踪</b><text>订单内直接处理</text></view>
    </view>

    <view class="section">
      <SectionHeader
        title="正在接单"
        description="认证陪玩 · 当前在线"
        action="查看全部 ›"
        @action="openDiscover"
      />
      <view v-if="loading" class="player-list">
        <view v-for="n in 3" :key="n" class="player-skeleton skeleton"></view>
      </view>
      <EmptyState
        v-else-if="!players.length"
        title="暂时没有在线大神"
        description="你可以先按服务下单，系统会自动匹配"
        symbol="⌁"
      />
      <view v-else class="player-list">
        <PlayerCard
          v-for="player in players"
          :key="player.id"
          :player="player"
          @open="openPlayer(player)"
        />
      </view>
    </view>
  </view>
</template>

<style scoped>
.home { padding-top:24rpx; }
.topbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:24rpx;
}
.hello,.brand { display:block; }
.hello { color:var(--muted); font-size:19rpx; }
.brand {
  margin-top:5rpx;
  color:var(--ink);
  font-size:28rpx;
  font-weight:900;
  letter-spacing:2rpx;
}
.shield {
  width:64rpx;
  height:64rpx;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius:22rpx;
  background:#fff;
  color:var(--brand);
  font-size:21rpx;
  font-weight:850;
  box-shadow:var(--shadow-card);
}
.hero {
  position:relative;
  overflow:hidden;
  padding:40rpx 34rpx 30rpx;
  border-radius:42rpx;
  background:linear-gradient(145deg,#191821 0%,#29243e 58%,#4c3e9d 125%);
  color:#fff;
  box-shadow:0 24rpx 72rpx rgba(31,26,59,.2);
}
.hero-glow { position:absolute; border-radius:50%; filter:blur(4rpx); }
.hero-glow.one {
  width:260rpx;height:260rpx;right:-70rpx;top:-90rpx;
  background:rgba(137,116,255,.23);
}
.hero-glow.two {
  width:170rpx;height:170rpx;left:-80rpx;bottom:-100rpx;
  background:rgba(83,218,169,.08);
}
.hero-copy { position:relative; z-index:1; }
.hero-kicker {
  display:block;
  color:#b8afef;
  font-size:18rpx;
  font-weight:700;
  letter-spacing:2rpx;
}
.hero-title {
  display:block;
  margin-top:14rpx;
  font-size:43rpx;
  font-weight:850;
  line-height:1.23;
  letter-spacing:-1rpx;
}
.hero-subtitle {
  display:block;
  margin-top:13rpx;
  color:#aaa8ba;
  font-size:20rpx;
}
.hero-actions { position:relative; z-index:1; display:flex; gap:12rpx; margin-top:34rpx; }
.hero-actions button {
  flex:1;
  height:auto;
  min-height:94rpx;
  margin:0;
  padding:17rpx 18rpx;
  display:flex;
  align-items:center;
  gap:12rpx;
  border-radius:25rpx;
  text-align:left;
}
.hero-actions button view { min-width:0; }
.hero-actions b,.hero-actions small { display:block; line-height:1.2; }
.hero-actions b { font-size:22rpx; }
.hero-actions small { margin-top:6rpx; font-size:16rpx; font-weight:500; opacity:.65; }
.hero-primary { background:#fff; color:#272232; }
.hero-secondary { background:rgba(255,255,255,.09); color:#fff; border:1rpx solid rgba(255,255,255,.08); }
.action-icon {
  width:42rpx;height:42rpx;flex:none;display:flex;align-items:center;justify-content:center;
  border-radius:14rpx;background:var(--brand-soft);color:var(--brand);font-size:20rpx;
}
.hero-secondary .action-icon { background:rgba(255,255,255,.1); color:#fff; }
.section { margin-top:40rpx; }
.game-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:14rpx; }
.game-card {
  min-height:160rpx;
  padding:22rpx;
  border:1rpx solid rgba(20,20,30,.035);
  border-radius:30rpx;
  background:#fff;
  box-shadow:var(--shadow-card);
}
.game-icon {
  width:62rpx;height:62rpx;display:flex;align-items:center;justify-content:center;
  border-radius:20rpx;font-size:25rpx;font-weight:850;
}
.tone-0 { background:#efedff;color:#6757e6; }
.tone-1 { background:#e9f8f1;color:#168d59; }
.tone-2 { background:#fff2e6;color:#b56c1a; }
.tone-3 { background:#eef4ff;color:#4271c8; }
.game-name { display:block; margin-top:17rpx; font-size:25rpx; font-weight:780; }
.game-more { display:block; margin-top:6rpx; color:var(--muted); font-size:17rpx; }
.game-skeleton { height:160rpx; border-radius:30rpx; }
.guarantee {
  display:flex;
  align-items:center;
  gap:12rpx;
  margin-top:22rpx;
  padding:22rpx 18rpx;
  border-radius:26rpx;
  background:#fff;
}
.guarantee>view:not(.divider) { flex:1; min-width:0; text-align:center; }
.guarantee b,.guarantee text { display:block; }
.guarantee b { color:var(--ink-2); font-size:17rpx; font-weight:750; }
.guarantee text { margin-top:4rpx; color:var(--muted-2); font-size:14rpx; white-space:nowrap; }
.divider { width:1rpx; height:34rpx; background:var(--line); }
.player-list { display:flex; flex-direction:column; gap:13rpx; }
.player-skeleton { height:154rpx; border-radius:30rpx; }
</style>
