<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import type { Game, PublicPlayer } from "../../types/domain"

const games = ref<Game[]>([])
const players = ref<PublicPlayer[]>([])
const selectedGameId = ref("")
const selectedRank = ref("")
const loading = ref(true)
const failed = ref(false)

const visiblePlayers = computed(() => {
  let list = players.value
  if (selectedRank.value) {
    list = list.filter(player =>
      player.skills.some(skill =>
        skill.rank === selectedRank.value &&
        (!selectedGameId.value || skill.game_id === selectedGameId.value)
      )
    )
  }
  return list
})

const ranks = computed(() => {
  const values = new Set<string>()
  for (const player of players.value) {
    for (const skill of player.skills) {
      if (!selectedGameId.value || skill.game_id === selectedGameId.value) {
        values.add(skill.rank)
      }
    }
  }
  return [...values].sort((a,b)=>a.localeCompare(b))
})

function lowestPrice(player: PublicPlayer) {
  const offerings = selectedGameId.value
    ? player.offerings.filter(item => item.game_id === selectedGameId.value)
    : player.offerings
  return offerings.length ? Math.min(...offerings.map(item => item.price)) : 0
}

async function loadPlayers() {
  loading.value = true
  failed.value = false
  selectedRank.value = ""
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

async function selectGame(id: string) {
  if (selectedGameId.value === id) return
  selectedGameId.value = id
  await loadPlayers()
}

function openPlayer(player: PublicPlayer) {
  uni.navigateTo({ url: `/pages/player/index?id=${player.id}` })
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
  <view class="page">
    <view class="hero">
      <text class="eyebrow">VERIFIED PLAYERS</text>
      <view class="title">发现大神</view>
      <view class="subtitle">只展示已认证、当前可接单且拥有有效服务 Offering 的陪玩。</view>
    </view>

    <scroll-view scroll-x class="filters" :show-scrollbar="false">
      <view class="filter-row">
        <text :class="{ active: !selectedGameId }" @click="selectGame('')">全部游戏</text>
        <text
          v-for="game in games"
          :key="game.id"
          :class="{ active: selectedGameId === game.id }"
          @click="selectGame(game.id)"
        >{{ game.name }}</text>
      </view>
    </scroll-view>

    <scroll-view v-if="ranks.length" scroll-x class="rank-filters" :show-scrollbar="false">
      <view class="filter-row rank-row">
        <text :class="{ active: !selectedRank }" @click="selectedRank=''">全部段位</text>
        <text
          v-for="rank in ranks"
          :key="rank"
          :class="{ active: selectedRank === rank }"
          @click="selectedRank=rank"
        >{{ rank }}</text>
      </view>
    </scroll-view>

    <view class="section-head">
      <view>
        <view class="section-title">可指定大神</view>
        <view class="section-desc">按评分排序 · 价格来自当前有效 Offering</view>
      </view>
      <text>{{ visiblePlayers.length }} 人</text>
    </view>

    <view v-if="loading" class="empty">正在加载大神…</view>
    <view v-else-if="failed" class="empty" @click="loadPlayers">加载失败，点此重试</view>
    <view v-else-if="!visiblePlayers.length" class="empty">当前筛选条件下暂无可接单大神</view>

    <view
      v-for="player in visiblePlayers"
      :key="player.id"
      class="player-card"
      @click="openPlayer(player)"
    >
      <image
        v-if="player.avatar_url"
        class="avatar"
        :src="player.avatar_url"
        mode="aspectFill"
      />
      <view v-else class="avatar fallback">{{ player.display_name.slice(0,1) }}</view>

      <view class="main">
        <view class="name-row">
          <text class="name">{{ player.display_name }}</text>
          <text class="available">可接单</text>
        </view>
        <view class="stats">
          {{ player.rating > 0 ? player.rating.toFixed(1) + " ★" : "新大神" }}
          · {{ player.review_count }} 评价
          · {{ player.order_count }} 单
        </view>

        <view class="skill-row">
          <text
            v-for="skill in player.skills.slice(0,3)"
            :key="skill.id"
            class="skill"
          >{{ skill.game_name }} {{ skill.rank }}</text>
        </view>

        <view class="bottom">
          <view>
            <text class="price">¥{{ (lowestPrice(player)/100).toFixed(2) }}</text>
            <text class="from"> 起</text>
          </view>
          <text class="cta">查看并指定 ›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height:100vh; padding:28rpx; background:#f6f6fa; box-sizing:border-box; }
.hero { padding:34rpx; border-radius:34rpx; background:linear-gradient(135deg,#17171f,#2c2940); color:#fff; }
.eyebrow { color:#9186e3; font-size:17rpx; font-weight:800; letter-spacing:3rpx; }
.title { margin-top:12rpx; font-size:42rpx; font-weight:850; }
.subtitle { margin-top:10rpx; color:#aaaab4; font-size:21rpx; line-height:1.55; }
.filters { margin-top:24rpx; width:100%; }
.rank-filters { margin-top:12rpx; width:100%; }
.filter-row { display:flex; gap:10rpx; white-space:nowrap; }
.filter-row text { flex:none; padding:13rpx 19rpx; border-radius:18rpx; background:#fff; color:#777783; font-size:20rpx; }
.filter-row text.active { background:#6c5ce7; color:#fff; font-weight:700; }
.rank-row text { padding:10rpx 16rpx; background:#ecebf2; font-size:18rpx; }
.section-head { display:flex; justify-content:space-between; align-items:flex-end; gap:20rpx; margin:34rpx 2rpx 18rpx; }
.section-title { font-size:30rpx; font-weight:800; }
.section-desc { margin-top:6rpx; color:#92929d; font-size:18rpx; }
.section-head>text { color:#92929d; font-size:19rpx; }
.player-card { display:flex; gap:20rpx; margin-bottom:16rpx; padding:26rpx; border-radius:30rpx; background:#fff; box-shadow:0 12rpx 36rpx rgba(25,20,60,.04); }
.avatar { width:102rpx; height:102rpx; flex:none; border-radius:30rpx; }
.avatar.fallback { display:flex; align-items:center; justify-content:center; background:#17171f; color:#fff; font-size:34rpx; font-weight:800; }
.main { flex:1; min-width:0; }
.name-row { display:flex; align-items:center; gap:10rpx; }
.name { font-size:28rpx; font-weight:800; }
.available { padding:5rpx 10rpx; border-radius:999rpx; background:#eafbf2; color:#24965d; font-size:16rpx; }
.stats { margin-top:7rpx; color:#858590; font-size:19rpx; }
.skill-row { display:flex; flex-wrap:wrap; gap:7rpx; margin-top:13rpx; }
.skill { padding:6rpx 10rpx; border-radius:11rpx; background:#f1efff; color:#6c5ce7; font-size:16rpx; }
.bottom { display:flex; align-items:flex-end; justify-content:space-between; gap:14rpx; margin-top:18rpx; padding-top:16rpx; border-top:1rpx solid #f0f0f4; }
.price { color:#17171f; font-size:29rpx; font-weight:850; }
.from { color:#92929d; font-size:17rpx; }
.cta { color:#6c5ce7; font-size:19rpx; font-weight:700; }
.empty { padding:70rpx 30rpx; border-radius:28rpx; background:#fff; color:#92929d; text-align:center; font-size:20rpx; }
</style>
