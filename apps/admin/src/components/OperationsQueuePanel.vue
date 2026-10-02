<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import OrderEvidencePanel from "./OrderEvidencePanel.vue"
import WithdrawalEvidencePanel from "./WithdrawalEvidencePanel.vue"

type Category = {
  kind: string
  label: string
  count: number
  breachedCount: number
  oldestAgeSeconds: number
  slaSeconds: number
  severity: "critical" | "warning"
}

type QueueItem = {
  kind: string
  severity: "critical" | "warning"
  entityId: string
  orderId?: string | null
  status: string
  statusCode?: string
  ageSeconds: number
  slaSeconds: number
  createdAt: string
  title: string
  detail: string
}

type QueueResponse = {
  generatedAt: string
  categories: Category[]
  items: QueueItem[]
}

const data = ref<QueueResponse>({
  generatedAt: "",
  categories: [],
  items: []
})
const loading = ref(true)
const error = ref("")
const orderEvidenceId = ref("")
const withdrawalEvidenceId = ref("")

const breachedTotal = computed(() =>
  data.value.categories.reduce((sum, item) => sum + item.breachedCount, 0)
)

const criticalTotal = computed(() =>
  data.value.items.filter(item => item.severity === "critical").length
)

function duration(seconds: number) {
  if (seconds < 60) return String(seconds) + "s"
  if (seconds < 3600) return String(Math.floor(seconds / 60)) + "m"
  if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return minutes ? String(hours) + "h " + String(minutes) + "m" : String(hours) + "h"
  }
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  return hours ? String(days) + "d " + String(hours) + "h" : String(days) + "d"
}

function ageRatio(item: QueueItem) {
  return Math.max(1, item.ageSeconds / Math.max(item.slaSeconds, 1))
}

function openEvidence(item: QueueItem) {
  if (item.kind === "WITHDRAWAL") {
    withdrawalEvidenceId.value = item.entityId
    return
  }
  if (item.orderId) {
    orderEvidenceId.value = item.orderId
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await adminRequest<QueueResponse>("/admin/operations/queue")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "运营待办加载失败"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="ops-home">
    <div class="hero">
      <div>
        <span class="eyebrow">OPERATIONS</span>
        <h2>运营待办</h2>
        <p>只展示超时或需要优先处理的异常项。</p>
      </div>
      <div class="hero-actions">
        <div>
          <span>已超时</span>
          <strong>{{ breachedTotal }}</strong>
        </div>
        <div class="critical">
          <span>高优先级</span>
          <strong>{{ criticalTotal }}</strong>
        </div>
        <button @click="load">刷新</button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="category-grid">
      <article
        v-for="category in data.categories"
        :key="category.kind"
        :class="{ breached: category.breachedCount > 0, critical: category.severity === 'critical' }"
      >
        <div class="category-head">
          <span>{{ category.label }}</span>
          <em>{{ category.severity }}</em>
        </div>
        <strong>{{ category.breachedCount }} / {{ category.count }}</strong>
        <small>
          最久 {{ duration(category.oldestAgeSeconds) }}
          · 参考时限 {{ duration(category.slaSeconds) }}
        </small>
      </article>
    </div>

    <section class="queue-panel">
      <header>
        <div>
          <h3>异常队列</h3>
          <p>优先展示最影响交付和资金处理的异常项。</p>
        </div>
        <span>{{ data.items.length }} 项</span>
      </header>

      <div v-if="loading" class="empty">正在加载运营待办…</div>
      <div v-else-if="!data.items.length" class="healthy">
        <b>当前没有超时待办</b>
        <span>仍需按正常运营节奏处理未超时的争议、提现和退款。</span>
      </div>

      <button
        v-for="item in data.items"
        :key="item.kind + ':' + item.entityId"
        class="queue-item"
        @click="openEvidence(item)"
      >
        <span class="severity" :class="item.severity">{{ item.severity }}</span>

        <span class="main">
          <span class="title-row">
            <b>{{ item.title }}</b>
            <em>{{ item.kind }}</em>
          </span>
          <small>{{ item.detail }}</small>
          <small v-if="item.orderId">order {{ item.orderId }}</small>
          <small v-else>entity {{ item.entityId }}</small>
        </span>

        <span class="age">
          <b>{{ duration(item.ageSeconds) }}</b>
          <small>超时 {{ ageRatio(item).toFixed(1) }}×</small>
          <em>{{ item.status }}</em>
        </span>
      </button>
    </section>

    <footer>
      更新时间 {{ data.generatedAt ? new Date(data.generatedAt).toLocaleString() : "—" }}
    </footer>

    <OrderEvidencePanel
      v-if="orderEvidenceId"
      :order-id="orderEvidenceId"
      @close="orderEvidenceId = ''"
    />

    <WithdrawalEvidencePanel
      v-if="withdrawalEvidenceId"
      :withdrawal-id="withdrawalEvidenceId"
      @close="withdrawalEvidenceId = ''"
    />
  </section>
</template>

<style scoped>
.ops-home { display:grid; gap:18px; }
.hero { display:flex; justify-content:space-between; align-items:center; gap:28px; padding:26px 28px; border-radius:22px; background:linear-gradient(135deg,#17171f,#2b283d); color:#fff; }
.eyebrow { color:#9186e3; font-size:10px; font-weight:900; letter-spacing:1.8px; }
h2 { margin:8px 0 0; font-size:26px; }
.hero p { margin:7px 0 0; color:#aaaab4; font-size:11px; }
.hero-actions { display:flex; align-items:center; gap:12px; }
.hero-actions>div { min-width:92px; padding:12px 14px; border-radius:14px; background:rgba(255,255,255,.07); }
.hero-actions span,.hero-actions strong { display:block; }
.hero-actions span { color:#aaaab4; font-size:9px; }
.hero-actions strong { margin-top:5px; font-size:22px; }
.hero-actions .critical strong { color:#ff9b9b; }
.hero-actions button { border:0; border-radius:11px; padding:11px 15px; background:#6c5ce7; color:#fff; cursor:pointer; font-weight:750; }
.error { padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.category-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; }
.category-grid article { min-height:120px; padding:17px; border:1px solid #ecebf1; border-radius:17px; background:#fff; }
.category-grid article.breached { border-color:#f0d8a3; background:#fffcf5; }
.category-grid article.breached.critical { border-color:#f0c3c3; background:#fff8f8; }
.category-head { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.category-head span { color:#6d6d78; font-size:10px; font-weight:750; }
.category-head em { font-size:8px; color:#9b9ba5; font-style:normal; text-transform:uppercase; }
.category-grid strong { display:block; margin-top:15px; font-size:26px; }
.category-grid small { display:block; margin-top:7px; color:#9696a0; font-size:9px; line-height:1.45; }
.queue-panel { padding:22px; border:1px solid #ecebf1; border-radius:20px; background:#fff; }
.queue-panel header { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:12px; }
.queue-panel h3 { margin:0; font-size:17px; }
.queue-panel header p { margin:6px 0 0; color:#92929d; font-size:11px; }
.queue-panel header>span { padding:6px 9px; border-radius:999px; background:#f2f1f7; color:#777783; font-size:9px; }
.empty,.healthy { padding:42px 20px; text-align:center; color:#92929d; font-size:11px; }
.healthy b,.healthy span { display:block; }
.healthy b { color:#2d8c60; font-size:14px; }
.healthy span { margin-top:7px; }
.queue-item { width:100%; display:grid; grid-template-columns:76px minmax(0,1fr) 110px; gap:14px; align-items:center; padding:15px 8px; border:0; border-top:1px solid #f0eff4; background:transparent; text-align:left; cursor:pointer; }
.queue-item:hover { background:#fafafd; }
.severity { justify-self:start; padding:6px 8px; border-radius:999px; font-size:8px; font-weight:850; text-transform:uppercase; }
.severity.critical { background:#fff0f0; color:#c63d3d; }
.severity.warning { background:#fff7dd; color:#9b7410; }
.main { min-width:0; }
.title-row { display:flex; align-items:center; gap:8px; }
.title-row b { font-size:11px; }
.title-row em { padding:3px 6px; border-radius:999px; background:#f2f1f7; color:#777783; font-size:8px; font-style:normal; }
.main small { display:block; margin-top:4px; color:#92929d; font-size:9px; overflow-wrap:anywhere; }
.age { text-align:right; }
.age b,.age small,.age em { display:block; }
.age b { font-size:13px; }
.age small { margin-top:3px; color:#a0a0aa; font-size:9px; }
.age em { margin-top:5px; color:#6c5ce7; font-size:8px; font-style:normal; }
footer { color:#aaaab4; font-size:9px; text-align:right; }
@media (max-width: 1300px) {
  .category-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
}
</style>
