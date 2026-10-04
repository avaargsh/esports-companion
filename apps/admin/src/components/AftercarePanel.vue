<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import OrderEvidencePanel from "./OrderEvidencePanel.vue"

type Dispute = {
  id: string
  order_id: string
  status: string
  statusCode?: string
  status_code?: string
  opened_by_role: string
  reason_code: string
  description: string
  held_amount: number
  resolution?: string | null
  created_at: string
  available_actions?: string[]
}

type Refund = {
  id: string
  order_id: string
  dispute_id: string
  amount: number
  status: string
  statusCode?: string
  status_code?: string
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

function stateCode(item: { status: string; statusCode?: string; status_code?: string }) {
  return item.statusCode || item.status_code || item.status
}

function hasAction(item: Dispute, action: string) {
  return item.available_actions?.includes(action) ?? false
}

const openDisputes = computed(() => disputes.value.filter(item => stateCode(item) === "OPEN"))
const activeRefunds = computed(() =>
  refunds.value.filter(item => !["COMPLETED", "FAILED", "REJECTED"].includes(stateCode(item)))
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

async function completeManualRefund(item: Refund) {
  if (busyId.value) return
  const providerRefundId = window.prompt(
    "请输入已完成退款的外部流水号 / 退款单号",
    item.out_refund_no || ""
  )
  if (providerRefundId === null) return
  const trimmed = providerRefundId.trim()
  if (!trimmed) {
    error.value = "请填写退款流水号后再确认完成"
    return
  }

  busyId.value = item.id
  error.value = ""
  try {
    await adminRequest(`/admin/refunds/${item.id}/complete`, {
      method: "POST",
      body: { provider_refund_id: trimmed }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "手工退款确认失败"
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
            <em :class="{ open: stateCode(item) === 'OPEN' }">{{ item.status }}</em>
          </div>
          <p>{{ item.reason_code }} · {{ item.opened_by_role }}</p>
          <div class="desc">{{ item.description || "未填写补充说明" }}</div>
          <small>冻结 ¥{{ (item.held_amount/100).toFixed(2) }} · {{ new Date(item.created_at).toLocaleString() }}</small>
        </div>
        <div v-if="stateCode(item) === 'OPEN'" class="case-actions">
          <button
            v-if="hasAction(item, 'RELEASE_PROVIDER')"
            class="secondary"
            :disabled="!!busyId"
            @click="resolveDispute(item,'release')"
          >继续结算</button>
          <button
            v-if="hasAction(item, 'REFUND_CUSTOMER')"
            class="danger"
            :disabled="!!busyId"
            @click="resolveDispute(item,'refund')"
          >批准退款</button>
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
              v-if="item.provider === 'MANUAL' && !['COMPLETED','FAILED','REJECTED'].includes(stateCode(item))"
              class="danger small"
              :disabled="!!busyId"
              @click="completeManualRefund(item)"
            >确认已退款</button>
            <button
              v-else-if="!['COMPLETED','FAILED'].includes(stateCode(item)) && item.provider !== 'MANUAL'"
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
.ops{display:grid;gap:22px}.error{padding:12px 14px;border:1px solid rgba(239,68,68,.18);border-radius:12px;background:rgba(239,68,68,.1);color:#f87171;font-size:12px}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.metrics article{padding:20px;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:#ffffff;box-shadow:0 10px 30px -5px rgba(0,0,0,.35)}.metrics span{color:#6b7280;font-size:11px}.metrics strong{display:block;margin-top:10px;color:#111827;font-size:26px}.panel{padding:24px;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:#ffffff;box-shadow:0 10px 30px -5px rgba(0,0,0,.12)}header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:18px}h2{margin:0;color:#111827;font-size:18px}header p{margin:6px 0 0;color:#6b7280;font-size:12px}.count{padding:7px 10px;border-radius:999px;background:rgba(0,0,0,.06);color:#111827;font-size:11px;font-weight:850}.case{display:flex;align-items:center;justify-content:space-between;gap:22px;padding:18px 4px;border-top:1px solid rgba(0,0,0,.06)}.case-main{min-width:0;flex:1}.case-top{display:flex;gap:10px;align-items:center}.order-link{border:0;padding:0;background:transparent;color:#111827;font-size:11px;font-weight:800;cursor:pointer;text-align:left}.case-top em,.row em{padding:4px 7px;border-radius:999px;background:#f3f4f6;color:#6b7280;font-size:10px;font-style:normal}.case-top em.open{background:rgba(0,0,0,.06);color:#111827}.case p{margin:7px 0;color:#6b7280;font-size:11px}.desc{max-width:760px;color:#111827;font-size:12px;line-height:1.55}.case small{display:block;margin-top:7px;color:#6b7280;font-size:10px}.case-actions{display:flex;gap:8px;flex:none}button{border:0;border-radius:10px;padding:8px 11px;cursor:pointer;font-weight:800}button:disabled{opacity:.45;cursor:not-allowed}.secondary{background:rgba(0,0,0,.06);color:#111827}.danger{background:rgba(239,68,68,.12);color:#f87171}.ghost{border:1px solid rgba(0,0,0,.10);background:#f3f4f6;color:#111827}.small{padding:6px 9px;font-size:10px}.resolution{color:#6b7280;font-size:11px}.empty{padding:34px;border:1px dashed rgba(0,0,0,.12);border-radius:14px;background:rgba(0,0,0,.04);color:#111827;text-align:center;font-size:12px}.table{overflow:hidden}.row{display:grid;grid-template-columns:1.5fr .7fr .8fr .8fr 1fr;gap:12px;align-items:center;min-height:58px;border-top:1px solid rgba(0,0,0,.06);color:#111827;font-size:11px}.row.head{min-height:36px;border:0;border-radius:10px;background:#f3f4f6;color:#374151;font-size:10px;font-weight:800}.row b,.row small{display:block}.row small{margin-top:4px;color:#6b7280;font-size:9px}
</style>
