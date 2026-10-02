<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import {
  adminRequest,
  clearAdminSession,
  getAdminAuthMode,
  isAdminSessionReady
} from "./api"
import AdminSessionPanel from "./components/AdminSessionPanel.vue"
import CatalogPanel from "./components/CatalogPanel.vue"
import OrderEvidencePanel from "./components/OrderEvidencePanel.vue"
import {
  ADMIN_NAV,
  type AdminSection
} from "./navigation"
import type {
  Order,
  Player,
  PlayerSkillReview,
  ReviewAction,
  Settlement
} from "./types/admin"
import DashboardWorkspace from "./workspaces/DashboardWorkspace.vue"
import FinanceWorkspace from "./workspaces/FinanceWorkspace.vue"
import OrdersWorkspace from "./workspaces/OrdersWorkspace.vue"
import PlayersWorkspace from "./workspaces/PlayersWorkspace.vue"

const tab = ref<AdminSection>("dashboard")
const authMode = getAdminAuthMode()
const authReady = ref(isAdminSessionReady())
const loading = ref(authReady.value)
const error = ref("")
const players = ref<Player[]>([])
const orders = ref<Order[]>([])
const settlements = ref<Settlement[]>([])
const skills = ref<PlayerSkillReview[]>([])
const evidenceOrderId = ref("")

const currentNav = computed(
  () => ADMIN_NAV.find(item => item.key === tab.value) ?? ADMIN_NAV[0]
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [nextPlayers, nextSkills, nextOrders, nextSettlements] =
      await Promise.all([
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

async function reviewPlayer(
  player: Player,
  action: ReviewAction
) {
  try {
    await adminRequest(`/admin/players/${player.id}/${action}`, {
      method: "POST"
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "审核失败"
  }
}

async function reviewSkill(
  skill: PlayerSkillReview,
  action: ReviewAction
) {
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
          v-for="item in ADMIN_NAV"
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
        <button
          v-if="authMode === 'bearer' && authReady"
          class="logout"
          @click="logoutAdmin"
        >
          退出
        </button>
      </div>
    </aside>

    <main>
      <header>
        <div>
          <p class="eyebrow">ESPORTS COMPANION</p>
          <h1>{{ currentNav.label }}</h1>
          <p class="section-description">{{ currentNav.description }}</p>
        </div>
        <button class="refresh" @click="load">刷新数据</button>
      </header>

      <AdminSessionPanel
        v-if="!authReady"
        @ready="onAdminSessionReady"
      />

      <template v-else>
        <div v-if="error" class="alert">{{ error }}</div>
        <div v-if="loading" class="loading">
          正在同步 Marketplace 状态...
        </div>

        <DashboardWorkspace
          v-else-if="tab === 'dashboard'"
          :orders="orders"
          :players="players"
          :settlements="settlements"
        />

        <OrdersWorkspace
          v-else-if="tab === 'orders'"
          :orders="orders"
          @open-evidence="evidenceOrderId = $event"
        />

        <PlayersWorkspace
          v-else-if="tab === 'players'"
          :players="players"
          :skills="skills"
          @review-player="reviewPlayer"
          @review-skill="reviewSkill"
        />

        <FinanceWorkspace
          v-else-if="tab === 'finance'"
          :settlements="settlements"
        />

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
.section-description { margin:8px 0 0;color:#92929d;font-size:12px; }
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
