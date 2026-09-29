<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "./api"
import CatalogPanel from "./components/CatalogPanel.vue"

type Player = {
  id: string
  userId: string
  displayName: string
  verificationStatus: string
  serviceStatus: string
  rating: number
  orderCount: number
}

type Order = {
  id: string
  orderNo: string
  userId: string
  status: string
  totalAmount: number
  version: number
  createdAt: string
}

type PlayerSkillReview = {
  id: string
  playerId: string
  playerName: string
  gameId: string
  gameName: string
  rank: string | null
  description: string
  evidenceUrl: string | null
  verificationStatus: string
  reviewNote: string
  updatedAt: string
}

type Settlement = {
  id: string
  orderId: string
  playerId: string
  grossAmount: number
  playerAmount: number
  platformFee: number
  status: string
}

type Tab = "dashboard" | "players" | "skills" | "catalog" | "orders" | "settlements"

const tab = ref<Tab>("dashboard")
const loading = ref(true)
const error = ref("")
const players = ref<Player[]>([])
const orders = ref<Order[]>([])
const settlements = ref<Settlement[]>([])
const skills = ref<PlayerSkillReview[]>([])

const nav = [
  { key: "dashboard" as const, label: "概览", icon: "◫" },
  { key: "players" as const, label: "陪玩审核", icon: "人" },
  { key: "skills" as const, label: "技能认证", icon: "证" },
  { key: "catalog" as const, label: "服务目录", icon: "目" },
  { key: "orders" as const, label: "订单管理", icon: "单" },
  { key: "settlements" as const, label: "结算中心", icon: "¥" }
]

const pendingPlayers = computed(() =>
  players.value.filter((item) => item.verificationStatus === "PENDING")
)

const gmv = computed(() =>
  orders.value.reduce((sum, item) => sum + item.totalAmount, 0)
)

const platformRevenue = computed(() =>
  settlements.value.reduce((sum, item) => sum + item.platformFee, 0)
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [nextPlayers, nextSkills, nextOrders, nextSettlements] = await Promise.all([
      adminRequest<Player[]>("/admin/players"),
      adminRequest<PlayerSkillReview[]>("/admin/player-skills"),
      adminRequest<Order[]>("/admin/orders"),
      adminRequest<Settlement[]>("/admin/settlements")
    ])
    players.value = nextPlayers
    skills.value = nextSkills
    orders.value = nextOrders
    settlements.value = nextSettlements
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "加载失败"
  } finally {
    loading.value = false
  }
}

async function reviewPlayer(player: Player, action: "approve" | "reject") {
  try {
    await adminRequest(`/admin/players/${player.id}/${action}`, {
      method: "POST"
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "审核失败"
  }
}

async function reviewSkill(skill: PlayerSkillReview, action: "approve" | "reject") {
  try {
    await adminRequest(`/admin/player-skills/${skill.id}/${action}`, {
      method: "POST"
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "技能审核失败"
  }
}

onMounted(load)
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">E</div>
        <div>
          <strong>Esports</strong>
          <span>Marketplace Admin</span>
        </div>
      </div>

      <nav>
        <button
          v-for="item in nav"
          :key="item.key"
          :class="{ active: tab === item.key }"
          @click="tab = item.key"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </nav>

      <div class="sidebar-foot">
        <span class="dot"></span>
        Demo Mode
      </div>
    </aside>

    <main>
      <header>
        <div>
          <p class="eyebrow">ESPORTS COMPANION</p>
          <h1>{{ nav.find((item) => item.key === tab)?.label }}</h1>
        </div>
        <button class="refresh" @click="load">刷新数据</button>
      </header>

      <div v-if="error" class="alert">{{ error }}</div>
      <div v-if="loading" class="loading">正在同步 Marketplace 状态...</div>

      <template v-else-if="tab === 'dashboard'">
        <section class="metric-grid">
          <article class="metric">
            <span>订单总数</span>
            <strong>{{ orders.length }}</strong>
            <small>当前 Demo 数据集</small>
          </article>
          <article class="metric">
            <span>GMV</span>
            <strong>¥{{ (gmv / 100).toFixed(2) }}</strong>
            <small>订单累计金额</small>
          </article>
          <article class="metric">
            <span>待审核陪玩</span>
            <strong>{{ pendingPlayers.length }}</strong>
            <small>需要运营处理</small>
          </article>
          <article class="metric accent">
            <span>平台服务费</span>
            <strong>¥{{ (platformRevenue / 100).toFixed(2) }}</strong>
            <small>已结算订单</small>
          </article>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Marketplace 状态</h2>
              <p>PostgreSQL durable state · Redis runtime acceleration</p>
            </div>
            <span class="healthy"><i></i> Demo Online</span>
          </div>
          <div class="flow">
            <span>WAITING_PAYMENT</span>
            <b>→</b>
            <span>MATCHING</span>
            <b>→</b>
            <span>ACCEPTED</span>
            <b>→</b>
            <span>IN_SERVICE</span>
            <b>→</b>
            <span>SETTLED</span>
          </div>
        </section>
      </template>

      <section v-else-if="tab === 'players'" class="panel">
        <div class="panel-head">
          <div>
            <h2>陪玩认证审核</h2>
            <p>申请通过后才能切换 AVAILABLE 并进入抢单市场。</p>
          </div>
          <span class="count">{{ players.length }} 人</span>
        </div>

        <div class="table">
          <div class="tr th">
            <span>陪玩</span><span>审核状态</span><span>接单状态</span><span>评分</span><span>操作</span>
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
                v-if="player.verificationStatus === 'PENDING'"
                class="approve"
                @click="reviewPlayer(player, 'approve')"
              >通过</button>
              <button
                v-if="player.verificationStatus === 'PENDING'"
                class="reject"
                @click="reviewPlayer(player, 'reject')"
              >拒绝</button>
              <small v-else>已处理</small>
            </span>
          </div>
        </div>
      </section>

      <section v-else-if="tab === 'skills'" class="panel">
        <div class="panel-head">
          <div>
            <h2>技能认证审核</h2>
            <p>段位或证明变化后会重新进入 PENDING，公开主页只展示 APPROVED 技能。</p>
          </div>
          <span class="count">{{ skills.filter(item => item.verificationStatus === "PENDING").length }} 待处理</span>
        </div>

        <div class="table">
          <div class="tr th">
            <span>陪玩 / 游戏</span><span>段位</span><span>证明</span><span>状态</span><span>操作</span>
          </div>
          <div v-for="skill in skills" :key="skill.id" class="tr">
            <span class="identity">
              <b>{{ skill.playerName }}</b>
              <small>{{ skill.gameName }}</small>
            </span>
            <span>{{ skill.rank || "-" }}</span>
            <span>
              <a v-if="skill.evidenceUrl" :href="skill.evidenceUrl" target="_blank" rel="noreferrer">查看证明</a>
              <small v-else>无</small>
            </span>
            <span><em class="badge">{{ skill.verificationStatus }}</em></span>
            <span class="actions">
              <button
                v-if="skill.verificationStatus === 'PENDING'"
                class="approve"
                @click="reviewSkill(skill, 'approve')"
              >通过</button>
              <button
                v-if="skill.verificationStatus === 'PENDING'"
                class="reject"
                @click="reviewSkill(skill, 'reject')"
              >拒绝</button>
              <small v-else>{{ skill.reviewNote || "已处理" }}</small>
            </span>
          </div>
        </div>
      </section>

      <CatalogPanel v-else-if="tab === 'catalog'" />

      <section v-else-if="tab === 'orders'" class="panel">
        <div class="panel-head">
          <div>
            <h2>订单查询</h2>
            <p>订单事实状态直接读取 PostgreSQL。</p>
          </div>
          <span class="count">{{ orders.length }} 单</span>
        </div>
        <div class="table orders">
          <div class="tr th">
            <span>订单号</span><span>状态</span><span>金额</span><span>版本</span><span>创建时间</span>
          </div>
          <div v-for="order in orders" :key="order.id" class="tr">
            <span class="identity"><b>{{ order.orderNo }}</b><small>{{ order.id.slice(0, 8) }}</small></span>
            <span><em class="badge purple">{{ order.status }}</em></span>
            <span>¥{{ (order.totalAmount / 100).toFixed(2) }}</span>
            <span>v{{ order.version }}</span>
            <span>{{ new Date(order.createdAt).toLocaleString() }}</span>
          </div>
        </div>
      </section>

      <section v-else class="panel">
        <div class="panel-head">
          <div>
            <h2>结算查看</h2>
            <p>Settlement 与 Ledger 是资金链的审计入口。</p>
          </div>
          <span class="count">{{ settlements.length }} 笔</span>
        </div>
        <div class="table settlements">
          <div class="tr th">
            <span>结算 ID</span><span>状态</span><span>订单金额</span><span>陪玩收入</span><span>平台服务费</span>
          </div>
          <div v-for="item in settlements" :key="item.id" class="tr">
            <span class="identity"><b>{{ item.id.slice(0, 12) }}</b><small>{{ item.orderId.slice(0, 8) }}</small></span>
            <span><em class="badge green">{{ item.status }}</em></span>
            <span>¥{{ (item.grossAmount / 100).toFixed(2) }}</span>
            <span>¥{{ (item.playerAmount / 100).toFixed(2) }}</span>
            <span>¥{{ (item.platformFee / 100).toFixed(2) }}</span>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style>
:root {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
  color: #17171f;
  background: #f6f6fa;
  font-synthesis: none;
}
* { box-sizing: border-box; }
body { margin: 0; min-width: 1100px; }
button { font: inherit; }
a { color: #6c5ce7; text-decoration: none; }
.shell { min-height: 100vh; display: grid; grid-template-columns: 250px minmax(0, 1fr); }
.sidebar { position: sticky; top: 0; height: 100vh; padding: 28px 20px; background: #17171f; color: white; display: flex; flex-direction: column; }
.brand { display: flex; align-items: center; gap: 12px; padding: 4px 8px 32px; }
.brand-mark { width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; background: linear-gradient(135deg, #6c5ce7, #8b7cf6); font-weight: 900; }
.brand strong, .brand span { display: block; }
.brand strong { font-size: 15px; }
.brand span { margin-top: 3px; color: #858591; font-size: 11px; }
nav { display: grid; gap: 8px; }
nav button { width: 100%; border: 0; padding: 13px 14px; border-radius: 13px; background: transparent; color: #9c9ca8; text-align: left; cursor: pointer; }
nav button.active { background: #292833; color: white; }
.nav-icon { display: inline-grid; width: 28px; height: 28px; margin-right: 9px; place-items: center; border-radius: 9px; background: #24232c; font-size: 12px; }
nav button.active .nav-icon { background: #6c5ce7; }
.sidebar-foot { margin-top: auto; padding: 14px; border-radius: 14px; background: #202028; color: #9c9ca8; font-size: 12px; }
.dot { display: inline-block; width: 8px; height: 8px; margin-right: 8px; border-radius: 50%; background: #22c55e; }
main { padding: 42px 50px 70px; }
header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 32px; }
.eyebrow { margin: 0 0 8px; color: #6c5ce7; font-size: 11px; font-weight: 800; letter-spacing: 2px; }
h1 { margin: 0; font-size: 34px; letter-spacing: -1px; }
.refresh { border: 1px solid #e4e3eb; padding: 10px 16px; border-radius: 12px; background: white; color: #585864; cursor: pointer; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.metric { min-height: 155px; padding: 24px; border: 1px solid #ecebf1; border-radius: 22px; background: white; box-shadow: 0 16px 45px rgba(30, 23, 70, .04); }
.metric span, .metric small { display: block; color: #92929d; font-size: 12px; }
.metric strong { display: block; margin: 18px 0 8px; font-size: 32px; }
.metric.accent { color: white; border: 0; background: linear-gradient(135deg, #6c5ce7, #8b7cf6); }
.metric.accent span, .metric.accent small { color: rgba(255,255,255,.75); }
.panel { margin-top: 22px; padding: 26px; border: 1px solid #ecebf1; border-radius: 22px; background: white; box-shadow: 0 16px 45px rgba(30,23,70,.035); }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.panel-head h2 { margin: 0; font-size: 18px; }
.panel-head p { margin: 7px 0 0; color: #92929d; font-size: 12px; }
.healthy, .count { padding: 8px 12px; border-radius: 999px; background: #f2f1f7; color: #686872; font-size: 11px; }
.healthy i { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: #22c55e; }
.flow { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 24px; border-radius: 16px; background: #f8f8fb; }
.flow span { padding: 9px 12px; border-radius: 10px; background: white; color: #6c5ce7; font-size: 11px; font-weight: 800; }
.flow b { color: #c0bfca; }
.table { width: 100%; overflow: hidden; }
.tr { display: grid; grid-template-columns: 1.5fr 1fr 1fr .7fr 1.2fr; align-items: center; gap: 14px; min-height: 66px; padding: 12px 8px; border-top: 1px solid #f0eff4; font-size: 12px; }
.tr.th { min-height: 42px; border: 0; color: #92929d; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.identity b, .identity small { display: block; }
.identity small { margin-top: 5px; color: #a6a5af; font-size: 10px; }
.badge { display: inline-block; padding: 6px 9px; border-radius: 999px; background: #fff7dd; color: #9b7410; font-style: normal; font-size: 10px; }
.badge.purple { background: #f1efff; color: #6c5ce7; }
.badge.green { background: #eafbf2; color: #198754; }
.actions { display: flex; gap: 7px; }
.actions button { border: 0; padding: 7px 10px; border-radius: 9px; cursor: pointer; font-size: 11px; }
.approve { background: #6c5ce7; color: white; }
.reject { background: #f2f1f5; color: #686872; }
.alert { margin-bottom: 18px; padding: 14px 16px; border-radius: 13px; background: #fff0f0; color: #c63d3d; font-size: 12px; }
.loading { padding: 70px; color: #92929d; text-align: center; }
@media (max-width: 1200px) {
  main { padding-left: 30px; padding-right: 30px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
