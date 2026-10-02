<script setup lang="ts">
import { ref } from "vue"

import type {
  Player,
  PlayerSkillReview,
  ReviewAction
} from "../types/admin"

defineProps<{
  players: Player[]
  skills: PlayerSkillReview[]
}>()

const emit = defineEmits<{
  "review-player": [player: Player, action: ReviewAction]
  "review-skill": [skill: PlayerSkillReview, action: ReviewAction]
}>()

type PlayerView = "players" | "skills"
const view = ref<PlayerView>("players")
</script>

<template>
  <div class="subnav">
    <button
      :class="{ active: view === 'players' }"
      @click="view = 'players'"
    >
      陪玩审核
    </button>
    <button
      :class="{ active: view === 'skills' }"
      @click="view = 'skills'"
    >
      技能认证
    </button>
  </div>

  <section v-if="view === 'players'" class="panel">
    <div class="panel-head">
      <div>
        <h2>陪玩审核</h2>
        <p>审核通过后才能进入接单市场。</p>
      </div>
      <span class="count">{{ players.length }} 人</span>
    </div>

    <div class="table">
      <div class="tr th">
        <span>陪玩</span>
        <span>审核状态</span>
        <span>接单状态</span>
        <span>评分</span>
        <span>操作</span>
      </div>
      <div v-for="player in players" :key="player.id" class="tr">
        <span class="identity">
          <b>{{ player.displayName }}</b>
          <small>{{ player.id.slice(0, 8) }}</small>
        </span>
        <span><em class="badge">{{ player.verificationStatus }}</em></span>
        <span>{{ player.serviceStatus }}</span>
        <span>{{ player.rating.toFixed(2) }}</span>
        <span class="actions">
          <template v-if="player.verificationStatus === 'PENDING'">
            <button
              class="approve"
              @click="emit('review-player', player, 'approve')"
            >
              通过
            </button>
            <button
              class="reject"
              @click="emit('review-player', player, 'reject')"
            >
              拒绝
            </button>
          </template>
          <small v-else>已处理</small>
        </span>
      </div>
    </div>
  </section>

  <section v-else class="panel">
    <div class="panel-head">
      <div>
        <h2>技能认证</h2>
        <p>公开主页只展示已通过认证的游戏技能。</p>
      </div>
      <span class="count">
        {{ skills.filter(item => item.verificationStatus === "PENDING").length }}
        待处理
      </span>
    </div>

    <div class="table">
      <div class="tr th">
        <span>陪玩 / 游戏</span>
        <span>段位</span>
        <span>证明</span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <div v-for="skill in skills" :key="skill.id" class="tr">
        <span class="identity">
          <b>{{ skill.playerName }}</b>
          <small>{{ skill.gameName }}</small>
        </span>
        <span>{{ skill.rank || "-" }}</span>
        <span>
          <a
            v-if="skill.evidenceUrl"
            :href="skill.evidenceUrl"
            target="_blank"
            rel="noreferrer"
          >
            查看证明
          </a>
          <small v-else>无</small>
        </span>
        <span><em class="badge">{{ skill.verificationStatus }}</em></span>
        <span class="actions">
          <template v-if="skill.verificationStatus === 'PENDING'">
            <button
              class="approve"
              @click="emit('review-skill', skill, 'approve')"
            >
              通过
            </button>
            <button
              class="reject"
              @click="emit('review-skill', skill, 'reject')"
            >
              拒绝
            </button>
          </template>
          <small v-else>{{ skill.reviewNote || "已处理" }}</small>
        </span>
      </div>
    </div>
  </section>
</template>
