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
        <view class="desc">开启后，匹配的订单才会出现在你的抢单大厅。</view>
      </view>
      <text class="count">{{ offerings.filter(item => item.status === "ACTIVE").length }} 已开启</text>
    </view>

    <view v-if="error" class="error">{{ error }}</view>

    <view v-for="sku in skus" :key="sku.id" class="sku-row">
      <view>
        <view class="sku-name">{{ sku.name }}</view>
        <view class="sku-meta">
          {{ gameNames.get(sku.game_id) || "游戏" }} · {{ sku.duration_minutes }} 分钟 · ¥{{ (sku.price / 100).toFixed(0) }}
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
.offering-card{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:27rpx;background:#191920;color:#fff}
.head{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx;padding-bottom:18rpx}.title{font-size:24rpx;font-weight:780}.desc{margin-top:6rpx;color:#777582;font-size:17rpx;line-height:1.45}.count{flex:none;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(103,87,230,.12);color:#a99cf7;font-size:16rpx;font-weight:700}
.sku-row{display:flex;align-items:center;justify-content:space-between;gap:16rpx;padding:19rpx 0;border-top:1rpx solid rgba(255,255,255,.05)}.sku-row>view{min-width:0}.sku-name{overflow:hidden;font-size:21rpx;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.sku-meta{margin-top:6rpx;color:#706e7a;font-size:16rpx}
.toggle{width:124rpx;height:58rpx;margin:0;line-height:58rpx;border-radius:18rpx;background:#24242d;color:#83818d;font-size:18rpx}.toggle.active{background:rgba(39,187,111,.11);color:#5ed28e}.error{margin-bottom:12rpx;padding:14rpx;border-radius:17rpx;background:rgba(239,68,68,.1);color:#dc7779;font-size:17rpx}
</style>