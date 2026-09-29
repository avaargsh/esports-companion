<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import {
  adminRequest,
  clearAdminSession,
  getAdminAuthMode,
  isAdminSessionReady
} from "./api"
import AdminSessionPanel from "./components/AdminSessionPanel.vue"
import AftercarePanel from "./components/AftercarePanel.vue"
import CatalogPanel from "./components/CatalogPanel.vue"
import OperationsQueuePanel from "./components/OperationsQueuePanel.vue"
import OrderEvidencePanel from "./components/OrderEvidencePanel.vue"
import WithdrawalsPanel from "./components/WithdrawalsPanel.vue"

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

type Tab = "dashboard" | "orders" | "players" | "finance" | "config"
type OrderView = "orders" | "aftercare"
type PlayerView = "players" | "skills"
type FinanceView = "withdrawals" | "settlements"

const tab = ref<Tab>("dashboard")
const orderView = ref<OrderView>("orders")
const playerView = ref<PlayerView>("players")
const financeView = ref<FinanceView>("withdrawals")

const authMode = getAdminAuthMode()
const authReady = ref(isAdminSessionReady())
const loading = ref(authReady.value)
const error = ref("")
const players = ref<Player[]>([])
const orders = ref<Order[]>([])
const settlements = ref<Settlement[]>([])
const skills = ref<PlayerSkillReview[]>([])
const evidenceOrderId = ref("")

const nav = [
  { key: "dashboard" as const, label: "概览", icon: "◫" },
  { key: "orders" as const, label: "订单", icon: "单" },
  { key: "players" as const, label: "陪玩", icon: "人" },
  { key: "finance" as const, label: "资金", icon: "¥" },
  { key: "config" as const, label: "配置", icon: "设" }
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

async function onAdminSessionReady() {
  authReady.value = true
  await load()
}

function logoutAdmin() {
  clearAdminSession()
  authReady.value = false
  error.value = ""
  loading.value = false
}

onMounted(() => {
  if (authReady.value) void load()
  else loading.value = false
})
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
        {{ authMode === "demo" ? "Demo Mode" : "Bearer Operator" }}
        <button v-if="authMode === 'bearer' && authReady" class="logout" @click="logoutAdmin">退出</button>
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

      <AdminSessionPanel v-if="!authReady" @ready="onAdminSessionReady" />

      <template v-else>
        <div v-if="error" class="alert">{{ error }}</div>
        <div v-if="loading" class="loading">正在同步 Marketplace 状态...</div>

        <template v-else-if="tab === 'dashboard'">
          <section class="metric-grid">
            <article class="metric">
              <span>订单总数</span>
              <strong>{{ orders.length }}</strong>
              <small>当前数据集</small>
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

          <OperationsQueuePanel />
        </template>

        <template v-else-if="tab === 'orders'">
          <div class="subnav">
            <button :class="{ active: orderView === 'orders' }" @click="orderView = 'orders'">订单列表</button>
            <button :class="{ active: orderView === 'aftercare' }" @click="orderView = 'aftercare'">售后 / 退款</button>
          </div>

          <section v-if="orderView === 'orders'" class="panel">
            <div class="panel-head">
              <div>
                <h2>订单</h2>
                <p>订单状态、聊天与审计事实统一从订单进入。</p>
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
                <span class="order-actions">
                  <small>{{ new Date(order.createdAt).toLocaleString() }}</small>
                  <button class="evidence-button" @click="evidenceOrderId = order.id">查看详情</button>
                </span>
              </div>
            </div>
          </section>

          <AftercarePanel v-else />
        </template>

        <template v-else-if="tab === 'players'">
          <div class="subnav">
            <button :class="{ active: playerView === 'players' }" @click="playerView = 'players'">陪玩审核</button>
            <button :class="{ active: playerView === 'skills' }" @click="playerView = 'skills'">技能认证</button>
          </div>

          <section v-if="playerView === 'players'" class="panel">
            <div class="panel-head">
              <div>
                <h2>陪玩审核</h2>
                <p>审核通过后才能进入接单市场。</p>
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

          <section v-else class="panel">
            <div class="panel-head">
              <div>
                <h2>技能认证</h2>
                <p>公开主页只展示已通过认证的游戏技能。</p>
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
        </template>

        <template v-else-if="tab === 'finance'">
          <div class="subnav">
            <button :class="{ active: financeView === 'withdrawals' }" @click="financeView = 'withdrawals'">提现</button>
            <button :class="{ active: financeView === 'settlements' }" @click="financeView = 'settlements'">结算</button>
          </div>

          <WithdrawalsPanel v-if="financeView === 'withdrawals'" />

          <section v-else class="panel">
            <div class="panel-head">
              <div>
                <h2>结算</h2>
                <p>Settlement 与 Ledger 保留为资金审计事实，不再作为独立产品入口。</p>
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
        </template>

        <CatalogPanel v-else-if="tab === 'config'" />
      </template>
    </main>

    <OrderEvidencePanel
      v-if="evidenceOrderId"
      :order-id="evidenceOrderId"
      @close="evidenceOrderId = ''"
    />
  </div>
</template>

<style>
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
  color: #17171f;
  background: #f6f6fa;
  font-synthesis: none;
}
* { box-sizing: border-box; }
body { margin: 0; min-width: 1100px; }
button { font: inherit; }
a { color: #6c5ce7; text-decoration: none; }
.shell { min-height: 100vh; display: grid; grid-template-columns: 226px minmax(0, 1fr); }
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
.sidebar-foot .logout { float:right; border:0; padding:0; background:transparent; color:#b8b8c2; cursor:pointer; font-size:11px; }
.dot { display: inline-block; width: 8px; height: 8px; margin-right: 8px; border-radius: 50%; background: #22c55e; }
main { padding: 42px 50px 70px; }
header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 32px; }
.eyebrow { margin: 0 0 8px; color: #6c5ce7; font-size: 11px; font-weight: 800; letter-spacing: 2px; }
h1 { margin: 0; font-size: 34px; letter-spacing: -1px; }
.refresh { border: 1px solid #e4e3eb; padding: 10px 16px; border-radius: 12px; background: white; color: #585864; cursor: pointer; }
.subnav { display:flex; gap:8px; margin-bottom:20px; padding:5px; width:max-content; border:1px solid #e8e7ee; border-radius:13px; background:#fff; }
.subnav button { border:0; padding:9px 14px; border-radius:9px; background:transparent; color:#82828d; cursor:pointer; font-size:12px; }
.subnav button.active { background:#17171f; color:#fff; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.metric { min-height: 145px; padding: 24px; border: 1px solid #ecebf1; border-radius: 22px; background: white; box-shadow: 0 16px 45px rgba(30, 23, 70, .04); }
.metric span, .metric small { display: block; color: #92929d; font-size: 12px; }
.metric strong { display: block; margin: 18px 0 8px; font-size: 32px; }
.metric.accent { color: white; border: 0; background: linear-gradient(135deg, #6c5ce7, #8b7cf6); }
.metric.accent span, .metric.accent small { color: rgba(255,255,255,.75); }
.panel { margin-top: 22px; padding: 26px; border: 1px solid #ecebf1; border-radius: 22px; background: white; box-shadow: 0 16px 45px rgba(30,23,70,.035); }
.subnav + .panel { margin-top:0; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.panel-head h2 { margin: 0; font-size: 18px; }
.panel-head p { margin: 7px 0 0; color: #92929d; font-size: 12px; }
.count { padding: 8px 12px; border-radius: 999px; background: #f2f1f7; color: #686872; font-size: 11px; }
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
.order-actions { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.order-actions small { color:#92929d; font-size:10px; }
.evidence-button { border:0; padding:6px 9px; border-radius:9px; background:#f1efff; color:#6c5ce7; cursor:pointer; font-size:10px; font-weight:700; }
.approve { background: #6c5ce7; color: white; }
.reject { background: #f2f1f5; color: #686872; }
.alert { margin-bottom: 18px; padding: 14px 16px; border-radius: 13px; background: #fff0f0; color: #c63d3d; font-size: 12px; }
.loading { padding: 70px; color: #92929d; text-align: center; }
@media (max-width: 1200px) {
  main { padding-left: 30px; padding-right: 30px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
