<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import OrderEvidencePanel from "./OrderEvidencePanel.vue"

type Dispute = {
  id: string
  order_id: string
  status: string
  opened_by_role: string
  reason_code: string
  description: string
  held_amount: number
  resolution?: string | null
  created_at: string
}

type Refund = {
  id: string
  order_id: string
  dispute_id: string
  amount: number
  status: string
  provider: string
  out_refund_no?: string | null
  provider_refund_id?: string | null
  completed_at?: string | null
}

const disputes = ref<Dispute[]>([])
const refunds = ref<Refund[]>([])
const error = ref("")
const busyId = ref("")
const evidenceOrderId = ref("")

const openDisputes = computed(() => disputes.value.filter(item => item.status === "OPEN"))
const activeRefunds = computed(() =>
  refunds.value.filter(item => !["COMPLETED", "FAILED", "REJECTED"].includes(item.status))
)

async function load() {
  error.value = ""
  try {
    const [nextDisputes, nextRefunds] = await Promise.all([
      adminRequest<Dispute[]>("/admin/disputes"),
      adminRequest<Refund[]>("/admin/refunds")
    ])
    disputes.value = nextDisputes
    refunds.value = nextRefunds
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "售后队列加载失败"
  }
}

async function resolveDispute(item: Dispute, action: "release" | "refund") {
  if (busyId.value) return
  busyId.value = item.id
  try {
    await adminRequest(`/admin/disputes/${item.id}/${action}`, { method: "POST" })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "处理失败"
  } finally {
    busyId.value = ""
  }
}

async function reconcileRefund(item: Refund) {
  if (busyId.value) return
  busyId.value = item.id
  try {
    await adminRequest(`/admin/refunds/${item.id}/reconcile`, { method: "POST" })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "退款查询失败"
  } finally {
    busyId.value = ""
  }
}

onMounted(load)
</script>

<template>
  <section class="ops">
    <div v-if="error" class="error">{{ error }}</div>

    <div class="metrics">
      <article><span>待处理争议</span><strong>{{ openDisputes.length }}</strong></article>
      <article><span>处理中退款</span><strong>{{ activeRefunds.length }}</strong></article>
      <article><span>冻结争议金额</span><strong>¥{{ (openDisputes.reduce((s,i)=>s+i.held_amount,0)/100).toFixed(2) }}</strong></article>
    </div>

    <section class="panel">
      <header>
        <div>
          <h2>售后争议</h2>
          <p>处理用户售后争议；无论继续结算还是退款都会保留审计记录。</p>
        </div>
        <button class="ghost" @click="load">刷新</button>
      </header>
      <div v-if="!disputes.length" class="empty">当前没有争议单</div>
      <div v-for="item in disputes" :key="item.id" class="case">
        <div class="case-main">
          <div class="case-top">
            <button class="order-link" @click="evidenceOrderId = item.order_id">
              订单 {{ item.order_id.slice(0, 12) }} · 查看事实
            </button>
            <em :class="{ open:item.status==='OPEN' }">{{ item.status }}</em>
          </div>
          <p>{{ item.reason_code }} · {{ item.opened_by_role }}</p>
          <div class="desc">{{ item.description || "未填写补充说明" }}</div>
          <small>冻结 ¥{{ (item.held_amount/100).toFixed(2) }} · {{ new Date(item.created_at).toLocaleString() }}</small>
        </div>
        <div v-if="item.status === 'OPEN'" class="case-actions">
          <button class="secondary" :disabled="!!busyId" @click="resolveDispute(item,'release')">继续结算</button>
          <button class="danger" :disabled="!!busyId" @click="resolveDispute(item,'refund')">批准退款</button>
        </div>
        <div v-else class="resolution">{{ item.resolution || "已处理" }}</div>
      </div>
    </section>

    <section class="panel">
      <header>
        <div>
          <h2>退款追踪</h2>
          <p>退款状态以支付渠道查询或回调为准，运营台不手工修改成功状态。</p>
        </div>
        <span class="count">{{ refunds.length }} 笔</span>
      </header>
      <div v-if="!refunds.length" class="empty">暂无退款记录</div>
      <div class="table" v-else>
        <div class="row head"><span>订单 / 退款</span><span>金额</span><span>退款渠道</span><span>状态</span><span>操作</span></div>
        <div v-for="item in refunds" :key="item.id" class="row">
          <span><b>{{ item.order_id.slice(0,10) }}</b><small>{{ item.id.slice(0,10) }}</small></span>
          <span>¥{{ (item.amount/100).toFixed(2) }}</span>
          <span>{{ item.provider }}</span>
          <span><em>{{ item.status }}</em></span>
          <span>
            <button
              v-if="!['COMPLETED','FAILED'].includes(item.status) && item.provider !== 'MANUAL'"
              class="ghost small"
              :disabled="!!busyId"
              @click="reconcileRefund(item)"
            >查询状态</button>
            <small v-else>{{ item.provider_refund_id || "—" }}</small>
          </span>
        </div>
      </div>
    </section>

    <OrderEvidencePanel
      v-if="evidenceOrderId"
      :order-id="evidenceOrderId"
      @close="evidenceOrderId = ''"
    />
  </section>
</template>

<style scoped>
.ops { display:grid; gap:22px; }
.error { padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.metrics { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
.metrics article { padding:20px; border:1px solid #ecebf1; border-radius:18px; background:#fff; }
.metrics span { color:#92929d; font-size:11px; }
.metrics strong { display:block; margin-top:10px; font-size:26px; }
.panel { padding:24px; border:1px solid #ecebf1; border-radius:20px; background:#fff; }
header { display:flex; justify-content:space-between; align-items:center; gap:20px; margin-bottom:18px; }
h2 { margin:0; font-size:18px; }
header p { margin:6px 0 0; color:#92929d; font-size:12px; }
.count { padding:7px 10px; border-radius:999px; background:#f2f1f7; color:#777783; font-size:11px; }
.case { display:flex; align-items:center; justify-content:space-between; gap:22px; padding:18px 4px; border-top:1px solid #f0eff4; }
.case-main { min-width:0; flex:1; }
.case-top { display:flex; gap:10px; align-items:center; }
.order-link { border:0; padding:0; background:transparent; color:#4d46a8; font-size:11px; font-weight:800; cursor:pointer; text-align:left; }
.case-top em, .row em { padding:4px 7px; border-radius:999px; background:#f2f1f5; color:#777783; font-size:10px; font-style:normal; }
.case-top em.open { background:#fff2d8; color:#a56d00; }
.case p { margin:7px 0; color:#6d6d78; font-size:11px; }
.desc { max-width:760px; color:#33333b; font-size:12px; line-height:1.55; }
.case small { display:block; margin-top:7px; color:#aaaab4; font-size:10px; }
.case-actions { display:flex; gap:8px; flex:none; }
button { border:0; border-radius:10px; padding:8px 11px; cursor:pointer; }
button:disabled { opacity:.45; cursor:not-allowed; }
.secondary { background:#f0edff; color:#6c5ce7; }
.danger { background:#fff0f0; color:#c63d3d; }
.ghost { border:1px solid #e5e4ec; background:#fff; color:#666672; }
.small { padding:6px 9px; font-size:10px; }
.resolution { color:#777783; font-size:11px; }
.empty { padding:34px; border-radius:14px; background:#fafafd; color:#9999a4; text-align:center; font-size:12px; }
.table { overflow:hidden; }
.row { display:grid; grid-template-columns:1.5fr .7fr .8fr .8fr 1fr; gap:12px; align-items:center; min-height:58px; border-top:1px solid #f0eff4; font-size:11px; }
.row.head { min-height:36px; border:0; color:#9999a4; font-size:10px; font-weight:800; }
.row b,.row small { display:block; }
.row small { margin-top:4px; color:#aaaab4; font-size:9px; }
</style>
