<script setup lang="ts">
import { computed, watch, ref } from "vue"

import { request } from "../../api/client"

type Game = {
  id: string
  name: string
}

type Sku = {
  id: string
  game_id: string
  name: string
  duration_minutes: number
  price: number
}

type Offering = {
  id: string
  player_id: string
  sku_id: string
  price_override: number | null
  description: string
  status: string
}

const props = defineProps<{ userId: string }>()

const games = ref<Game[]>([])
const skus = ref<Sku[]>([])
const offerings = ref<Offering[]>([])
const busySku = ref("")
const error = ref("")

const gameNames = computed(() => {
  const map = new Map<string, string>()
  for (const game of games.value) map.set(game.id, game.name)
  return map
})

const offeringBySku = computed(() => {
  const map = new Map<string, Offering>()
  for (const offering of offerings.value) map.set(offering.sku_id, offering)
  return map
})

async function load() {
  if (!props.userId) return
  error.value = ""
  try {
    games.value = await request<Game[]>("/games")
    const groups = await Promise.all(
      games.value.map((game) =>
        request<Sku[]>(`/games/${game.id}/skus`)
      )
    )
    skus.value = groups.flat()
    offerings.value = await request<Offering[]>("/player/offerings", {
      userId: props.userId
    })
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "OFFERING_LOAD_FAILED"
  }
}

async function toggle(sku: Sku) {
  if (busySku.value) return
  busySku.value = sku.id
  const existing = offeringBySku.value.get(sku.id)
  const nextStatus = existing?.status === "ACTIVE" ? "INACTIVE" : "ACTIVE"
  try {
    await request<Offering>(`/player/offerings/${sku.id}`, {
      method: "PUT",
      userId: props.userId,
      data: {
        price_override: existing?.price_override ?? null,
        description: existing?.description ?? "",
        status: nextStatus
      }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "OFFERING_UPDATE_FAILED"
  } finally {
    busySku.value = ""
  }
}

watch(() => props.userId, () => { void load() }, { immediate: true })
</script>

<template>
  <view class="offering-card">
    <view class="head">
      <view>
        <view class="title">可接服务</view>
        <view class="desc">只有开启的 SKU 才会出现在你的抢单池。</view>
      </view>
      <text class="count">{{ offerings.filter(item => item.status === "ACTIVE").length }} 已开启</text>
    </view>

    <view v-if="error" class="error">{{ error }}</view>

    <view v-for="sku in skus" :key="sku.id" class="sku-row">
      <view>
        <view class="sku-name">{{ sku.name }}</view>
        <view class="sku-meta">
          {{ gameNames.get(sku.game_id) || "Game" }} · {{ sku.duration_minutes }} 分钟 · ¥{{ (sku.price / 100).toFixed(0) }}
        </view>
      </view>
      <button
        class="toggle"
        :class="{ active: offeringBySku.get(sku.id)?.status === 'ACTIVE' }"
        :loading="busySku === sku.id"
        @click="toggle(sku)"
      >
        {{ offeringBySku.get(sku.id)?.status === "ACTIVE" ? "已开启" : "未开启" }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.offering-card { margin-top: 24rpx; padding: 28rpx; border-radius: 28rpx; background: #181820; color: #fff; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20rpx; padding-bottom: 20rpx; }
.title { font-size: 28rpx; font-weight: 700; }
.desc { margin-top: 7rpx; color: #777784; font-size: 20rpx; }
.count { color: #8f82ff; font-size: 20rpx; }
.sku-row { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; padding: 22rpx 0; border-top: 1rpx solid rgba(255,255,255,.06); }
.sku-name { font-size: 24rpx; font-weight: 600; }
.sku-meta { margin-top: 7rpx; color: #777784; font-size: 19rpx; }
.toggle { width: 142rpx; margin: 0; height: 62rpx; line-height: 62rpx; border-radius: 20rpx; background: #25252e; color: #8d8d98; font-size: 20rpx; }
.toggle.active { background: rgba(108,92,231,.18); color: #9e92ff; }
.error { margin-bottom: 12rpx; padding: 16rpx; border-radius: 18rpx; background: rgba(239,68,68,.12); color: #ff9292; font-size: 19rpx; }
</style>
