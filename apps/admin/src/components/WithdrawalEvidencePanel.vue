<script setup lang="ts">
import { ref, watch } from "vue"

import { adminRequest } from "../api"

type Evidence = {
  withdrawal: {
    id: string
    userId: string
    amount: number
    status: string
    provider: string
    providerTxnId?: string | null
    failureReason?: string | null
    createdAt: string
    completedAt?: string | null
    rejectedAt?: string | null
  }
  wallet: {
    id: string
    availableBalance: number
    frozenBalance: number
    version: number
  } | null
  ledger: Array<{
    id: string
    entryType: string
    amount: number
    balanceAfter: number
    createdAt: string
  }>
}

const props = defineProps<{ withdrawalId: string }>()
const emit = defineEmits<{ close: [] }>()

const data = ref<Evidence | null>(null)
const loading = ref(false)
const error = ref("")

function money(value: number | undefined) {
  return "¥" + (((value ?? 0) / 100).toFixed(2))
}

function time(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

async function load() {
  if (!props.withdrawalId) return
  loading.value = true
  error.value = ""
  try {
    data.value = await adminRequest<Evidence>(
      "/admin/withdrawals/" + props.withdrawalId + "/evidence"
    )
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提现对账信息加载失败"
  } finally {
    loading.value = false
  }
}

watch(() => props.withdrawalId, () => { void load() }, { immediate: true })
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <aside class="drawer">
      <header>
        <div>
          <span class="eyebrow">WITHDRAWAL EVIDENCE</span>
          <h2>提现对账</h2>
          <p>{{ withdrawalId }}</p>
        </div>
        <button class="close" @click="emit('close')">关闭</button>
      </header>

      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="loading" class="loading">正在读取 Wallet / Ledger…</div>

      <template v-else-if="data">
        <section class="summary">
          <article>
            <span>申请金额</span>
            <strong>{{ money(data.withdrawal.amount) }}</strong>
            <small>{{ data.withdrawal.status }}</small>
          </article>
          <article>
            <span>可用余额</span>
            <strong>{{ money(data.wallet?.availableBalance) }}</strong>
            <small>Wallet v{{ data.wallet?.version ?? "—" }}</small>
          </article>
          <article>
            <span>冻结余额</span>
            <strong>{{ money(data.wallet?.frozenBalance) }}</strong>
            <small>资金状态以 Ledger 为证据</small>
          </article>
        </section>

        <section class="facts">
          <div><span>用户</span><b>{{ data.withdrawal.userId }}</b></div>
          <div><span>Provider</span><b>{{ data.withdrawal.provider }}</b></div>
          <div><span>外部流水</span><b>{{ data.withdrawal.providerTxnId || "尚未完成打款" }}</b></div>
          <div><span>申请时间</span><b>{{ time(data.withdrawal.createdAt) }}</b></div>
          <div><span>完成时间</span><b>{{ time(data.withdrawal.completedAt) }}</b></div>
          <div v-if="data.withdrawal.failureReason">
            <span>拒绝原因</span><b>{{ data.withdrawal.failureReason }}</b>
          </div>
        </section>

        <section class="ledger">
          <div class="ledger-head">
            <div>
              <h3>Ledger Evidence</h3>
              <p>只展示 biz_type=WITHDRAWAL 且 biz_id 等于当前提现 ID 的账本记录。</p>
            </div>
            <span>{{ data.ledger.length }} 条</span>
          </div>

          <div v-if="!data.ledger.length" class="empty">没有找到对应账本记录</div>
          <div v-for="entry in data.ledger" :key="entry.id" class="entry">
            <div>
              <b>{{ entry.entryType }}</b>
              <small>{{ time(entry.createdAt) }}</small>
            </div>
            <div class="money">
              <strong>{{ entry.amount > 0 ? "+" : "" }}{{ money(entry.amount) }}</strong>
              <small>balanceAfter {{ money(entry.balanceAfter) }}</small>
            </div>
          </div>
        </section>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position:fixed; inset:0; z-index:55; background:rgba(15,15,21,.38); display:flex; justify-content:flex-end; }
.drawer { width:min(620px,64vw); height:100vh; overflow:auto; padding:28px; background:#f7f7fa; box-shadow:-24px 0 70px rgba(20,18,40,.14); }
header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
.eyebrow { color:#6c5ce7; font-size:10px; font-weight:900; letter-spacing:1.8px; }
h2 { margin:8px 0 0; font-size:24px; }
header p { margin:6px 0 0; color:#9999a4; font-size:10px; overflow-wrap:anywhere; }
.close { border:1px solid #dfdee7; border-radius:10px; padding:8px 12px; background:#fff; color:#666672; cursor:pointer; }
.error { margin-top:18px; padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.loading,.empty { padding:34px 18px; color:#9999a4; text-align:center; font-size:12px; }
.summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:22px; }
.summary article { padding:18px; border:1px solid #ecebf1; border-radius:16px; background:#fff; }
.summary span,.summary small { display:block; color:#92929d; font-size:10px; }
.summary strong { display:block; margin:9px 0 5px; font-size:18px; }
.facts,.ledger { margin-top:14px; padding:20px; border:1px solid #ecebf1; border-radius:18px; background:#fff; }
.facts div { display:grid; grid-template-columns:90px 1fr; gap:12px; padding:8px 0; font-size:11px; }
.facts span { color:#92929d; }
.facts b { overflow-wrap:anywhere; }
.ledger-head { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:14px; }
.ledger-head h3 { margin:0; font-size:15px; }
.ledger-head p { margin:6px 0 0; color:#92929d; font-size:10px; line-height:1.5; }
.ledger-head>span { padding:5px 8px; border-radius:999px; background:#f2f1f7; color:#777783; font-size:9px; }
.entry { display:flex; justify-content:space-between; gap:16px; padding:13px 0; border-top:1px solid #f0eff4; }
.entry b,.entry small,.money strong { display:block; }
.entry b { font-size:11px; }
.entry small { margin-top:4px; color:#9999a4; font-size:9px; }
.money { text-align:right; }
.money strong { font-size:12px; }
</style>
