<script setup lang="ts">
import { computed, ref, watch } from "vue"

import { request } from "../../api/client"
import type { Game, PlayerSkill } from "../../types/domain"

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
      request<Game[]>("/games"),
      request<PlayerSkill[]>("/player/skills", { userId: props.userId })
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
    await request<PlayerSkill>(`/player/skills/${gameId.value}`, {
      method: "PUT",
      userId: props.userId,
      data: {
        rank: rank.value.trim(),
        description: description.value.trim(),
        evidence_url: evidenceUrl.value.trim()
      }
    })
    rank.value = ""
    evidenceUrl.value = ""
    description.value = ""
    await load()
    uni.showToast({ title: "已提交审核", icon: "success" })
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
        <view class="skill-name">{{ gameNames.get(skill.game_id) || "Game" }} · {{ skill.rank || "-" }}</view>
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
        提交 / 重新认证
      </button>
    </view>
  </view>
</template>

<style scoped>
.skill-card { margin-top: 24rpx; padding: 28rpx; border-radius: 28rpx; background: #181820; color: #fff; }
.head { display: flex; justify-content: space-between; gap: 20rpx; padding-bottom: 20rpx; }
.title { font-size: 28rpx; font-weight: 700; }
.desc { margin-top: 7rpx; color: #777784; font-size: 20rpx; line-height: 1.5; }
.count { color: #65e39b; font-size: 20rpx; white-space: nowrap; }
.skill-row { padding: 20rpx 0; border-top: 1rpx solid rgba(255,255,255,.06); }
.skill-name { font-size: 24rpx; font-weight: 650; }
.skill-meta { margin-top: 8rpx; color: #777784; font-size: 19rpx; }
.status.approved { color: #65e39b; }
.status.pending { color: #f2bd5a; }
.status.rejected { color: #ff9292; }
.form { display: grid; gap: 14rpx; padding-top: 22rpx; border-top: 1rpx solid rgba(255,255,255,.06); }
.picker, input, textarea { width: 100%; padding: 20rpx; border-radius: 18rpx; background: #25252e; color: #fff; box-sizing: border-box; font-size: 21rpx; }
textarea { height: 120rpx; }
.submit { margin: 0; height: 72rpx; line-height: 72rpx; border-radius: 20rpx; background: #6c5ce7; color: #fff; font-size: 22rpx; }
.submit[disabled] { opacity: .45; }
.error { margin-bottom: 14rpx; color: #ff9292; font-size: 19rpx; }
</style>
