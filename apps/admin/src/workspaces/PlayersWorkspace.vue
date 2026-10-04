<script setup lang="ts">
import { computed, ref } from "vue"

import type {
  Player,
  PlayerServiceUpdateAction,
  PlayerSkillReview,
  ReviewAction
} from "../types/admin"

const props = defineProps<{
  players: Player[]
  skills: PlayerSkillReview[]
}>()

const emit = defineEmits<{
  "review-player": [player: Player, action: ReviewAction]
  "review-skill": [skill: PlayerSkillReview, action: ReviewAction]
  "update-player-service": [player: Player, action: PlayerServiceUpdateAction]
}>()

type PlayerView = "players" | "skills" | "directory"
const view = ref<PlayerView>("players")

const pendingSkillCount = computed(() =>
  props.skills.filter(item => item.verificationStatusCode === "PENDING").length
)

const approvedPlayerCount = computed(() =>
  props.players.filter(item => item.verificationStatusCode === "APPROVED").length
)

function playerActions(player: Player) {
  return player.availableActions ?? []
}

function playerServiceActions(player: Player) {
  return player.serviceActions ?? []
}

function skillActions(skill: PlayerSkillReview) {
  return skill.availableActions ?? []
}
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
    <button
      :class="{ active: view === 'directory' }"
      @click="view = 'directory'"
    >
      陪玩列表与封禁
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
          <button
            v-if="playerActions(player).includes('APPROVE')"
            class="approve"
            @click="emit('review-player', player, 'approve')"
          >
            通过
          </button>
          <button
            v-if="playerActions(player).includes('REJECT')"
            class="reject"
            @click="emit('review-player', player, 'reject')"
          >
            驳回
          </button>
          <button
            v-if="playerActions(player).includes('CANCEL')"
            class="reject"
            @click="emit('review-player', player, 'cancel')"
          >
            取消资格
          </button>
          <button
            v-if="playerActions(player).includes('RESTORE')"
            class="approve"
            @click="emit('review-player', player, 'restore')"
          >
            恢复资格
          </button>
          <small v-if="playerActions(player).length === 0">已处理</small>
        </span>
      </div>
    </div>
  </section>

  <section v-else-if="view === 'skills'" class="panel">
    <div class="panel-head">
      <div>
        <h2>技能认证</h2>
        <p>公开主页只展示已通过认证的游戏技能。</p>
      </div>
      <span class="count">
        {{ pendingSkillCount }}
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
          <button
            v-if="skillActions(skill).includes('APPROVE')"
            class="approve"
            @click="emit('review-skill', skill, 'approve')"
          >
            通过
          </button>
          <button
            v-if="skillActions(skill).includes('REJECT')"
            class="reject"
            @click="emit('review-skill', skill, 'reject')"
          >
            驳回
          </button>
          <button
            v-if="skillActions(skill).includes('REVOKE')"
            class="reject"
            @click="emit('review-skill', skill, 'revoke')"
          >
            撤销
          </button>
          <small v-if="skillActions(skill).length === 0">{{ skill.reviewNote || "已处理" }}</small>
        </span>
      </div>
    </div>
  </section>

  <section v-else class="panel">
    <div class="panel-head">
      <div>
        <h2>陪玩列表与封禁</h2>
        <p>管理已入驻陪玩的接单权限，停用后不会进入小程序找大神列表。</p>
      </div>
      <span class="count">{{ approvedPlayerCount }} 已通过</span>
    </div>

    <div class="table">
      <div class="tr th">
        <span>陪玩</span>
        <span>审核状态</span>
        <span>接单状态</span>
        <span>成交 / 评分</span>
        <span>操作</span>
      </div>
      <div v-for="player in players" :key="`directory-${player.id}`" class="tr">
        <span class="identity">
          <b>{{ player.displayName }}</b>
          <small>{{ player.id.slice(0, 8) }}</small>
        </span>
        <span><em class="badge">{{ player.verificationStatus }}</em></span>
        <span>{{ player.serviceStatus }}</span>
        <span>{{ player.orderCount }} 单 / {{ player.rating.toFixed(2) }}</span>
        <span class="actions">
          <button
            v-if="playerServiceActions(player).includes('SUSPEND')"
            class="reject"
            @click="emit('update-player-service', player, 'suspend')"
          >
            停用接单
          </button>
          <button
            v-if="playerServiceActions(player).includes('ACTIVATE')"
            class="approve"
            @click="emit('update-player-service', player, 'activate')"
          >
            恢复接单
          </button>
          <button
            v-if="playerActions(player).includes('CANCEL')"
            class="reject soft"
            @click="emit('review-player', player, 'cancel')"
          >
            取消资格
          </button>
          <button
            v-if="playerActions(player).includes('RESTORE')"
            class="approve soft"
            @click="emit('review-player', player, 'restore')"
          >
            恢复资格
          </button>
          <small v-if="playerServiceActions(player).length === 0 && playerActions(player).length === 0">无可用操作</small>
        </span>
      </div>
    </div>
  </section>
</template>
