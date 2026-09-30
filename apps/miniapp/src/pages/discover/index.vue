<script setup lang="ts">
import { ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import EmptyState from "../../components/EmptyState.vue"
import PlayerCard from "../../components/PlayerCard.vue"
import type { Game, PublicPlayer } from "../../types/domain"\nimport { navigation } from "../../platform/navigation"

const games = ref<Game[]>([])
const players = ref<PublicPlayer[]>([])
const selectedGameId = ref("")
const loading = ref(true)
const failed = ref(false)

async function loadPlayers() {
  loading.value = true
  failed.value = false
  try {
    const suffix = selectedGameId.value
      ? `?limit=30&game_id=${encodeURIComponent(selectedGameId.value)}`
      : "?limit=30"
    players.value = await request<PublicPlayer[]>(`/players${suffix}`)
  } catch {
    failed.value = true
    players.value = []
  } finally {
    loading.value = false
  }
}
async function selectGame(id:string) {
  if (selectedGameId.value === id) return
  selectedGameId.value = id
  await loadPlayers()
}
function openPlayer(player:PublicPlayer) {
  navigation.push("/pages/player/index", { id: player.id })
}
onLoad(async query => {
  selectedGameId.value = String(query?.gameId || "")
  try {
    games.value = await request<Game[]>("/games")
    await loadPlayers()
  } catch {
    failed.value = true
    loading.value = false
  }
})
</script>

<template>
  <view class="safe-page discover">
    <view class="intro">
      <text class="eyebrow">VERIFIED PLAYERS</text>
      <text class="title">找一个合拍的大神</text>
      <text class="subtitle">只展示已认证、当前可接单的陪玩。</text>
    </view>

    <scroll-view scroll-x class="filters" :show-scrollbar="false">
      <view class="filter-row">
        <text :class="{active:!selectedGameId}" @click="selectGame('')">全部</text>
        <text
          v-for="game in games"
          :key="game.id"
          :class="{active:selectedGameId===game.id}"
          @click="selectGame(game.id)"
        >{{ game.name }}</text>
      </view>
    </scroll-view>

    <view class="summary">
      <text>{{ loading ? "正在刷新" : players.length + " 位可接单" }}</text>
      <text class="hint">按综合体验展示</text>
    </view>

    <view v-if="loading" class="list">
      <view v-for="n in 5" :key="n" class="skeleton row-skeleton"></view>
    </view>
    <EmptyState
      v-else-if="failed"
      title="加载失败"
      description="网络恢复后重新加载"
      action="重试"
      symbol="↻"
      @action="loadPlayers"
    />
    <EmptyState
      v-else-if="!players.length"
      title="这个游戏暂时没有在线大神"
      description="可以换个游戏，或从首页直接按服务下单"
      symbol="⌁"
    />
    <view v-else class="list">
      <PlayerCard
        v-for="player in players"
        :key="player.id"
        :player="player"
        :game-id="selectedGameId"
        @open="openPlayer(player)"
      />
    </view>
  </view>
</template>

<style scoped>
.discover { padding-top:22rpx; }
.intro { padding:18rpx 4rpx 28rpx; }
.eyebrow { display:block;color:var(--brand);font-size:16rpx;font-weight:800;letter-spacing:2rpx; }
.title { display:block;margin-top:10rpx;font-size:39rpx;font-weight:850;letter-spacing:-1rpx; }
.subtitle { display:block;margin-top:9rpx;color:var(--muted);font-size:20rpx; }
.filters { width:100%; margin-bottom:24rpx; }
.filter-row { display:flex; gap:9rpx; padding-right:28rpx; white-space:nowrap; }
.filter-row text {
  flex:none;padding:13rpx 20rpx;border:1rpx solid #e7e6ed;border-radius:18rpx;
  background:#fff;color:#70707b;font-size:20rpx;
}
.filter-row text.active {
  border-color:var(--ink);background:var(--ink);color:#fff;font-weight:750;
}
.summary { display:flex;justify-content:space-between;align-items:center;margin:0 3rpx 16rpx;color:var(--ink-2);font-size:19rpx;font-weight:700; }
.summary .hint { color:var(--muted);font-weight:500; }
.list { display:flex; flex-direction:column; gap:13rpx; }
.row-skeleton { height:154rpx; border-radius:30rpx; }
</style>
