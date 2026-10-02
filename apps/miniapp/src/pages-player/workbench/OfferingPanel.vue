<script setup lang="ts">
import { computed, watch, ref } from "vue"

import { listGames, listGameSkus } from "../../domain/catalog/api"
import {
  listPlayerOfferings,
  listPlayerSkills,
  updatePlayerOffering,
  type PlayerOffering
} from "../../domain/player/api"
import type { Game, PlayerSkill, ServiceSku } from "../../types/domain"

const props = defineProps<{ userId: string; playerApproved?: boolean }>()

const games = ref<Game[]>([])
const skus = ref<ServiceSku[]>([])
const offerings = ref<PlayerOffering[]>([])
const skills = ref<PlayerSkill[]>([])
const busySku = ref("")
const error = ref("")

const gameNames = computed(() => {
  const map = new Map<string, string>()
  for (const game of games.value) map.set(game.id, game.name)
  return map
})

const offeringBySku = computed(() => {
  const map = new Map<string, PlayerOffering>()
  for (const offering of offerings.value) map.set(offering.sku_id, offering)
  return map
})

const approvedGameIds = computed(() =>
  new Set(
    skills.value
      .filter(item => (item.verification_status_code || item.verification_status) === "APPROVED")
      .map(item => item.game_id)
  )
)

const activeCertifiedOfferings = computed(() =>
  offerings.value.filter((item) => {
    if (item.status !== "ACTIVE") return false
    const sku = skus.value.find(next => next.id === item.sku_id)
    return Boolean(sku && approvedGameIds.value.has(sku.game_id))
  })
)

const canManageOfferings = computed(() =>
  props.playerApproved === true && approvedGameIds.value.size > 0
)

function skuLockedReason(sku: ServiceSku) {
  if (props.playerApproved !== true) return "陪玩身份通过后才可开启"
  if (!approvedGameIds.value.has(sku.game_id)) return "该游戏技能认证通过后才可开启"
  return ""
}

async function load() {
  if (!props.userId) return
  error.value = ""
  try {
    games.value = await listGames()
    const groups = await Promise.all(
      games.value.map(game => listGameSkus(game.id))
    )
    skus.value = groups.flat()
    const [nextOfferings, nextSkills] = await Promise.all([
      listPlayerOfferings(props.userId),
      listPlayerSkills(props.userId)
    ])
    offerings.value = nextOfferings
    skills.value = nextSkills
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "OFFERING_LOAD_FAILED"
  }
}

async function toggle(sku: ServiceSku) {
  const reason = skuLockedReason(sku)
  if (reason) {
    error.value = reason
    return
  }
  if (busySku.value) return
  busySku.value = sku.id
  const existing = offeringBySku.value.get(sku.id)
  const nextStatus = existing?.status === "ACTIVE" ? "INACTIVE" : "ACTIVE"
  try {
    await updatePlayerOffering(props.userId, sku.id, {
      priceOverride: existing?.price_override ?? null,
      description: existing?.description ?? "",
      status: nextStatus
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
      <text class="count">{{ activeCertifiedOfferings.length }} 已开启</text>
    </view>

    <view v-if="error" class="error">{{ error }}</view>
    <view v-if="!canManageOfferings" class="locked">通过陪玩身份审核并完成至少一个技能认证后，才可以开启可接服务。</view>

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
        :disabled="!!skuLockedReason(sku)"
        @click="toggle(sku)"
      >
        {{ skuLockedReason(sku) || (offeringBySku.get(sku.id)?.status === "ACTIVE" ? "已开启" : "未开启") }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.offering-card{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(0,0,0,.06);border-radius:27rpx;background:var(--inverse-surface);color:#fff}
.head{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx;padding-bottom:18rpx}.title{font-size:24rpx;font-weight:780}.desc{margin-top:6rpx;color:#777582;font-size:17rpx;line-height:1.45}.count{flex:none;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(103,87,230,.12);color:var(--brand-on-inverse);font-size:16rpx;font-weight:700}
.sku-row{display:flex;align-items:center;justify-content:space-between;gap:16rpx;padding:19rpx 0;border-top:1rpx solid rgba(0,0,0,.06)}.sku-row>view{min-width:0}.sku-name{overflow:hidden;font-size:21rpx;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.sku-meta{margin-top:6rpx;color:#706e7a;font-size:16rpx}
.toggle{min-width:124rpx;height:58rpx;margin:0;padding:0 16rpx;line-height:58rpx;border-radius:18rpx;background:var(--inverse-control-strong);color:#83818d;font-size:18rpx}.toggle.active{background:rgba(39,187,111,.11);color:var(--success-on-inverse)}.toggle[disabled]{background:rgba(255,255,255,.08);color:#777582;opacity:1}.error,.locked{margin-bottom:12rpx;padding:14rpx;border-radius:17rpx;background:rgba(239,68,68,.1);color:var(--danger-on-inverse);font-size:17rpx}.locked{background:rgba(255,255,255,.08);color:#c8c5cf}
</style>