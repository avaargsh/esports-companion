<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import WithdrawalEvidencePanel from "./WithdrawalEvidencePanel.vue"

type Withdrawal = {
  id: string
  userId: string
  amount: number
  status: string
  provider: string
  providerTxnId?: string | null
  failureReason?: string | null
  createdAt: string
}

const items = ref<Withdrawal[]>([])
const error = ref("")
const busyId = ref("")
const evidenceId = ref("")

const pending = computed(() => items.value.filter(item => item.status === "PENDING"))
const pendingAmount = computed(() => pending.value.reduce((sum,item)=>sum+item.amount,0))

async function load() {
  error.value = ""
  try {
    items.value = await adminRequest<Withdrawal[]>("/admin/withdrawals")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提现队列加载失败"
  }
}

async function act(item: Withdrawal, action: "complete" | "reject") {
  if (busyId.value) return
  let body: unknown = undefined
  if (action === "complete") {
    const payoutRef = window.prompt("请输入真实外部打款流水号 / 凭证号")
    if (payoutRef === null) return
    const normalized = payoutRef.trim()
    if (!normalized) {
      error.value = "确认打款前必须填写真实外部流水号"
      return
    }
    if (!window.confirm("确认外部打款已经成功？提交后资金会解除冻结并记为 COMPLETED。")) return
    body = { provider_txn_id: normalized }
  }

  let suffix = ""
  if (action === "reject") {
    const reason = window.prompt("请输入拒绝原因", "REJECTED_BY_PLATFORM")
    if (reason === null) return
    suffix = `?reason=${encodeURIComponent(reason || "REJECTED_BY_PLATFORM")}`
  }

  busyId.value = item.id
  try {
    await adminRequest("/admin/withdrawals/" + item.id + "/" + action + suffix, {
      method: "POST",
      body
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提现处理失败"
  } finally {
    busyId.value = ""
  }
}

onMounted(load)
</script>

<template>
  <section class="withdrawals">
    <div v-if="error" class="error">{{ error }}</div>

    <div class="summary">
      <article><span>待审核</span><strong>{{ pending.length }}</strong></article>
      <article><span>待打款金额</span><strong>¥{{ (pendingAmount/100).toFixed(2) }}</strong></article>
      <article><span>处理模式</span><strong class="manual">MANUAL</strong></article>
    </div>

    <section class="panel">
      <header>
        <div>
          <h2>提现审核</h2>
          <p>申请时资金已从 available 冻结；确认完成必须填写真实外部打款流水号。</p>
        </div>
        <button class="ghost" @click="load">刷新</button>
      </header>

      <div v-if="!items.length" class="empty">暂无提现记录</div>
      <div v-else class="table">
        <div class="row head"><span>用户 / 申请</span><span>金额</span><span>Provider</span><span>状态</span><span>操作</span></div>
        <div v-for="item in items" :key="item.id" class="row">
          <span><b>{{ item.userId.slice(0,10) }}</b><small>{{ new Date(item.createdAt).toLocaleString() }}</small></span>
          <span class="amount">¥{{ (item.amount/100).toFixed(2) }}</span>
          <span>{{ item.provider }}</span>
          <span><em :class="{ pending:item.status==='PENDING' }">{{ item.status }}</em></span>
          <span class="actions">
            <template v-if="item.status === 'PENDING'">
              <button class="complete" :disabled="!!busyId" @click="act(item,'complete')">录入流水并完成</button>
              <button class="reject" :disabled="!!busyId" @click="act(item,'reject')">拒绝</button>
            </template>
            <small v-else>{{ item.providerTxnId || item.failureReason || "已处理" }}</small>
            <button class="evidence" @click="evidenceId = item.id">对账</button>
          </span>
        </div>
      </div>
    </section>

    <WithdrawalEvidencePanel
      v-if="evidenceId"
      :withdrawal-id="evidenceId"
      @close="evidenceId = ''"
    />
  </section>
</template>

<style scoped>
.withdrawals { display:grid; gap:22px; }
.error { padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }
.summary article { padding:20px; border:1px solid #ecebf1; border-radius:18px; background:#fff; }
.summary span { color:#92929d; font-size:11px; }
.summary strong { display:block; margin-top:10px; font-size:26px; }
.summary .manual { color:#6c5ce7; font-size:18px; }
.panel { padding:24px; border:1px solid #ecebf1; border-radius:20px; background:#fff; }
header { display:flex; justify-content:space-between; align-items:center; gap:20px; margin-bottom:18px; }
h2 { margin:0; font-size:18px; }
header p { margin:6px 0 0; color:#92929d; font-size:12px; }
.ghost { border:1px solid #e5e4ec; background:#fff; color:#666672; }
.empty { padding:34px; border-radius:14px; background:#fafafd; color:#9999a4; text-align:center; font-size:12px; }
.row { display:grid; grid-template-columns:1.5fr .8fr .8fr .8fr 1.5fr; gap:12px; align-items:center; min-height:62px; border-top:1px solid #f0eff4; font-size:11px; }
.row.head { min-height:36px; border:0; color:#9999a4; font-size:10px; font-weight:800; }
.row b,.row small { display:block; }
.row small { margin-top:4px; color:#aaaab4; font-size:9px; }
.amount { font-weight:800; }
em { display:inline-block; padding:5px 8px; border-radius:999px; background:#f2f1f5; color:#777783; font-size:10px; font-style:normal; }
em.pending { background:#fff2d8; color:#a56d00; }
.actions { display:flex; gap:6px; align-items:center; }
button { border:0; border-radius:9px; padding:7px 9px; cursor:pointer; font-size:10px; }
button:disabled { opacity:.45; cursor:not-allowed; }
.complete { background:#6c5ce7; color:#fff; }
.reject { background:#f2f1f5; color:#686872; }
.evidence { border:1px solid #dfdee7; background:#fff; color:#6c5ce7; }
</style>
