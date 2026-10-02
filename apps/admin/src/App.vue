<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import {
  adminRequest,
  clearAdminSession,
  getAdminAuthMode,
  isAdminSessionReady
} from "./api"
import AdminSessionPanel from "./components/AdminSessionPanel.vue"
import AppSidebar from "./components/AppSidebar.vue"
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
import UsersWorkspace from "./workspaces/UsersWorkspace.vue"
import MarketingWorkspace from "./workspaces/MarketingWorkspace.vue"
import SystemWorkspace from "./workspaces/SystemWorkspace.vue"

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

function decisionBody(action: ReviewAction, fallback: string) {
  if (!["reject", "cancel", "revoke"].includes(action)) return undefined
  const reason = window.prompt("请输入处理原因", fallback)?.trim()
  if (!reason) return null
  return { reason }
}

async function reviewPlayer(
  player: Player,
  action: ReviewAction
) {
  const body = decisionBody(action, action === "cancel" ? "资格已取消" : "资料未通过")
  if (body === null) return
  try {
    await adminRequest(`/admin/players/${player.id}/${action}`, {
      method: "POST",
      body: body ?? undefined
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
  const body = decisionBody(action, action === "revoke" ? "认证资格撤销" : "认证材料不符合要求")
  if (body === null) return
  try {
    await adminRequest(`/admin/player-skills/${skill.id}/${action}`, {
      method: "POST",
      body: body ?? undefined
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
    <AppSidebar
      :items="ADMIN_NAV"
      :active="tab"
      :auth-label="authMode === 'demo' ? 'Demo Mode' : '微信管理员'"
      :can-logout="authMode === 'bearer' && authReady"
      @select="tab = $event"
      @logout="logoutAdmin"
    />

    <main>
      <header class="top-header">
        <div class="title-group">
          <div class="breadcrumb">
            <span>若水电竞</span>
            <i></i>
            <span>{{ currentNav.label }}</span>
          </div>
          <p class="eyebrow">ESPORTS COMPANION</p>
          <h1>{{ currentNav.label }}</h1>
          <p class="section-description">{{ currentNav.description }}</p>
        </div>
        <div class="header-tools">
          <label class="global-search">
            <img src="https://img.icons8.com/fluency/96/search.png" alt="搜索" />
            <input placeholder="搜索订单、陪玩、用户" />
          </label>
          <span class="mode-badge"><span></span>{{ authMode === "demo" ? "Demo 模式" : "真实账号" }}</span>
          <button class="bell" type="button" aria-label="系统通知">
            <img src="https://img.icons8.com/fluency/96/appointment-reminders.png" alt="通知" />
          </button>
          <button class="refresh" @click="load">刷新数据</button>
          <div class="admin-avatar">
            <img src="https://img.icons8.com/fluency/96/admin-settings-male.png" alt="管理员" />
          </div>
        </div>
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

        <UsersWorkspace v-else-if="tab === 'users'" />

        <MarketingWorkspace v-else-if="tab === 'marketing'" />

        <SystemWorkspace v-else-if="tab === 'system'" />
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
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;color:#111827;background:#f7f7f8;font-synthesis:none;--ink:#111827;--gold:#111827;--gold-deep:#000000;--green:#111827;--orange:#111827;--red:#ef4444;--bg:#f7f7f8;--sidebar:#0f0f10;--panel:#ffffff;--panel-2:#f3f4f6;--line:rgba(0,0,0,.10);--gold-line:rgba(0,0,0,.10);--muted:#6b7280;--shadow:0 10px 30px -5px rgba(0,0,0,.5)}*{box-sizing:border-box}body{margin:0;min-width:1180px;background:var(--bg)}button,input,select,textarea{font:inherit}button{cursor:pointer}a{color:var(--ink);text-decoration:none}.shell{min-height:100vh;display:grid;grid-template-columns:auto minmax(0,1fr);background:radial-gradient(circle at 35% -10%,rgba(0,0,0,.05),transparent 30%),#f7f7f8}main{min-width:0;padding:34px 42px 60px}.top-header{display:flex;justify-content:space-between;align-items:flex-end;gap:26px;margin-bottom:28px}.title-group{min-width:0}.breadcrumb{display:flex;align-items:center;gap:9px;margin-bottom:12px;color:#6b7280;font-size:12px}.breadcrumb i{width:5px;height:5px;border-radius:999px;background:rgba(0,0,0,.45)}.eyebrow{margin:0 0 8px;color:var(--ink);font-size:11px;font-weight:850;letter-spacing:2px}h1{margin:0;color:#111827;font-size:34px;letter-spacing:0}.section-description{margin:8px 0 0;color:#6b7280;font-size:12px}.header-tools{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}.global-search{width:260px;height:40px;display:flex;align-items:center;gap:9px;padding:0 12px;border:1px solid var(--line);border-radius:12px;background:#ffffff;transition:border-color .16s ease,box-shadow .16s ease}.global-search:focus-within{border-color:rgba(0,0,0,.20);box-shadow:0 0 0 3px rgba(0,0,0,.06)}.global-search img{width:18px;height:18px}.global-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:#111827;font-size:12px}.global-search input::placeholder{color:#6b7280}.mode-badge{height:40px;display:flex;align-items:center;gap:8px;padding:0 13px;border:1px solid rgba(0,0,0,.10);border-radius:999px;background:rgba(0,0,0,.06);color:#111827;font-size:12px;font-weight:800}.mode-badge span{width:8px;height:8px;border-radius:999px;background:#111827;box-shadow:0 0 14px rgba(16,185,129,.85)}.bell,.refresh,.admin-avatar{height:40px;border:1px solid var(--line);border-radius:12px;background:#ffffff;color:#111827}.bell{width:40px;display:grid;place-items:center}.bell img,.admin-avatar img{width:21px;height:21px}.refresh{padding:0 16px;color:var(--ink);font-size:12px;font-weight:800}.admin-avatar{width:40px;display:grid;place-items:center;overflow:hidden}.subnav{display:flex;gap:8px;margin-bottom:20px;padding:5px;width:max-content;border:1px solid var(--line);border-radius:13px;background:#ffffff}.subnav button{border:0;padding:9px 14px;border-radius:9px;background:transparent;color:#6b7280;cursor:pointer;font-size:12px}.subnav button.active{background:linear-gradient(135deg,#111827,#000000);color:#fff;font-weight:850;box-shadow:0 10px 24px rgba(0,0,0,.12)}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}.metric{min-height:145px;padding:24px;border:1px solid var(--line);border-radius:16px;background:#ffffff;box-shadow:var(--shadow)}.metric span,.metric small{display:block;color:#6b7280;font-size:12px}.metric strong{display:block;margin:18px 0 8px;color:#111827;font-size:32px}.metric.gold strong{color:var(--ink)}.metric.warning strong{color:var(--ink)}.metric.accent{border-color:rgba(0,0,0,.10);background:linear-gradient(135deg,rgba(0,0,0,.08),#ffffff 48%,#f3f4f6)}.metric.accent strong{color:var(--ink)}.panel{margin-top:22px;padding:26px;border:1px solid var(--line);border-radius:16px;background:#ffffff;box-shadow:var(--shadow)}.subnav+.panel{margin-top:0}.panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}.panel-head h2{margin:0;color:#111827;font-size:18px}.panel-head p{margin:7px 0 0;color:#6b7280;font-size:12px}.count{padding:8px 12px;border-radius:999px;background:rgba(0,0,0,.06);color:var(--ink);font-size:11px;font-weight:800}.table{width:100%;overflow:hidden}.tr{display:grid;grid-template-columns:1.5fr 1fr 1fr .7fr 1.2fr;align-items:center;gap:14px;min-height:66px;padding:12px 8px;border-top:1px solid rgba(0,0,0,.06);color:#111827;font-size:12px}.tr.th{min-height:42px;border:0;border-radius:10px;background:#f3f4f6;color:#374151;font-size:10px;font-weight:800;text-transform:uppercase}.identity b,.identity small{display:block}.identity small{margin-top:5px;color:#6b7280;font-size:10px}.badge,.status-chip{display:inline-block;padding:6px 9px;border-radius:999px;background:rgba(0,0,0,.06);color:#111827;font-style:normal;font-size:10px;font-weight:850}.badge.purple{background:rgba(0,0,0,.06);color:#111827}.badge.green{background:rgba(0,0,0,.08);color:#111827}.actions{display:flex;gap:7px}.actions button{border:0;padding:7px 10px;border-radius:9px;cursor:pointer;font-size:11px;font-weight:800}.order-actions{display:flex;align-items:center;justify-content:space-between;gap:8px}.order-actions small{color:#6b7280;font-size:10px}.evidence-button{border:0;padding:6px 9px;border-radius:9px;background:rgba(0,0,0,.06);color:var(--ink);cursor:pointer;font-size:10px;font-weight:800}.approve{background:rgba(0,0,0,.08);color:#111827}.reject{background:rgba(239,68,68,.12);color:#f87171}.alert{margin-bottom:18px;padding:14px 16px;border:1px solid rgba(239,68,68,.18);border-radius:13px;background:rgba(239,68,68,.1);color:#f87171;font-size:12px}.loading{padding:70px;color:#6b7280;text-align:center}.flow{display:flex;gap:12px;align-items:center;padding:30px 24px}.flow span{padding:10px 14px;border-radius:12px;background:#f3f4f6;color:#111827;font-size:12px;font-weight:700}.flow i{color:#6b7280;font-style:normal}table{width:100%;border-collapse:collapse}th,td{padding:15px 24px;border-bottom:1px solid rgba(0,0,0,.06);text-align:left;color:#111827;font-size:12px}th{background:#f3f4f6;color:#374151;font-size:11px;font-weight:700}td b{display:block;font-weight:700}td small{display:block;margin-top:4px;color:#6b7280}.muted{color:#6b7280}.error{margin:20px 0;padding:16px 18px;border:1px solid rgba(239,68,68,.18);border-radius:14px;background:rgba(239,68,68,.1);color:#f87171;font-size:13px}input,select,textarea{border:1px solid var(--line);background:#f3f4f6;color:#111827}input:focus,select:focus,textarea:focus{outline:none;border-color:rgba(0,0,0,.20);box-shadow:0 0 0 3px rgba(0,0,0,.06)}@media(max-width:1200px){main{padding-left:30px;padding-right:30px}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.top-header{align-items:flex-start;flex-direction:column}.header-tools{justify-content:flex-start}.global-search{width:320px}}
</style>\n