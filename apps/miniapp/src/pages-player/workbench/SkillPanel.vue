<script setup lang="ts">
import { computed, ref, watch } from "vue"

import { listGames } from "../../domain/catalog/api"
import {
  listPlayerSkills,
  upsertPlayerSkill
} from "../../domain/player/api"
import type { Game, PlayerSkill } from "../../types/domain"
import { showSuccess } from "../../ui/feedback"

const props = defineProps<{ userId: string }>()

const games = ref<Game[]>([])
const skills = ref<PlayerSkill[]>([])
const gameId = ref("")
const rank = ref("")
const evidenceUrl = ref("")
const description = ref("")
const busy = ref(false)
const error = ref("")

const gameNames = computed(() => {
  const map = new Map<string, string>()
  for (const game of games.value) map.set(game.id, game.name)
  return map
})

async function load() {
  if (!props.userId) return
  error.value = ""
  try {
    const [gameRows, skillRows] = await Promise.all([
      listGames(),
      listPlayerSkills(props.userId)
    ])
    games.value = gameRows
    skills.value = skillRows
    if (!gameId.value && games.value.length) gameId.value = games.value[0].id
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "SKILL_LOAD_FAILED"
  }
}

async function submit() {
  if (!props.userId || !gameId.value || !rank.value.trim() || !evidenceUrl.value.trim()) return
  busy.value = true
  error.value = ""
  try {
    await upsertPlayerSkill(props.userId, gameId.value, {
      rank: rank.value.trim(),
      description: description.value.trim(),
      evidenceUrl: evidenceUrl.value.trim()
    })
    rank.value = ""
    evidenceUrl.value = ""
    description.value = ""
    await load()
    showSuccess("已提交审核")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "SKILL_SUBMIT_FAILED"
  } finally {
    busy.value = false
  }
}

watch(() => props.userId, () => { void load() }, { immediate: true })
</script>

<template>
  <view class="skill-card">
    <view class="head">
      <view>
        <view class="title">技能认证</view>
        <view class="desc">提交游戏段位与证明；审核通过后展示在大神主页。</view>
      </view>
      <text class="count">{{ skills.filter(item => item.verification_status === "APPROVED").length }} 已认证</text>
    </view>

    <view v-if="error" class="error">{{ error }}</view>

    <view v-for="skill in skills" :key="skill.id" class="skill-row">
      <view class="skill-main">
        <view class="skill-name">{{ gameNames.get(skill.game_id) || "游戏" }} · {{ skill.rank || "-" }}</view>
        <view class="skill-meta">
          <text :class="['status', skill.verification_status.toLowerCase()]">
            {{ skill.verification_status === "APPROVED" ? "已认证" : skill.verification_status === "PENDING" ? "审核中" : "未通过" }}
          </text>
          <text v-if="skill.review_note"> · {{ skill.review_note }}</text>
        </view>
      </view>
    </view>

    <view class="form">
      <picker
        mode="selector"
        :range="games"
        range-key="name"
        @change="gameId = games[Number($event.detail.value)]?.id || gameId"
      >
        <view class="picker">{{ gameNames.get(gameId) || "选择游戏" }}</view>
      </picker>
      <input v-model="rank" maxlength="80" placeholder="当前段位，例如：王者 50 星" />
      <input v-model="evidenceUrl" maxlength="512" placeholder="段位证明图片 URL" />
      <textarea v-model="description" maxlength="500" placeholder="补充说明（选填）" />
      <button class="submit" :loading="busy" :disabled="!rank.trim() || !evidenceUrl.trim()" @click="submit">
        提交认证
      </button>
    </view>
  </view>
</template>

<style scoped>
.skill-card{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:27rpx;background:var(--inverse-surface);color:#fff}.head{display:flex;justify-content:space-between;gap:18rpx;padding-bottom:18rpx}.title{font-size:24rpx;font-weight:780}.desc{margin-top:6rpx;color:#777582;font-size:17rpx;line-height:1.45}.count{flex:none;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(39,187,111,.1);color:var(--success-on-inverse);font-size:16rpx;font-weight:700}
.skill-row{padding:17rpx 0;border-top:1rpx solid rgba(255,255,255,.05)}.skill-name{font-size:21rpx;font-weight:700}.skill-meta{margin-top:6rpx;color:#706e7a;font-size:16rpx}.status.approved{color:var(--success-on-inverse)}.status.pending{color:var(--warning-on-inverse)}.status.rejected{color:var(--danger-on-inverse)}
.form{display:grid;gap:11rpx;padding-top:19rpx;border-top:1rpx solid rgba(255,255,255,.05)}.picker,input,textarea{width:100%;padding:18rpx;border:1rpx solid rgba(255,255,255,.03);border-radius:18rpx;background:var(--inverse-control);color:#fff;font-size:19rpx}.picker{color:#d6d3df}textarea{height:112rpx}.submit{height:70rpx;margin:2rpx 0 0;line-height:70rpx;border-radius:20rpx;background:var(--brand);color:#fff;font-size:20rpx;font-weight:750}.submit[disabled]{opacity:.4}.error{margin-bottom:12rpx;color:var(--danger-on-inverse);font-size:17rpx}
</style>