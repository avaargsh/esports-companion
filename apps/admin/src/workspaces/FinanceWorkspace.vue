<script setup lang="ts">
import { onMounted, ref } from "vue"

import { adminRequest } from "../api"
import WithdrawalsPanel from "../components/WithdrawalsPanel.vue"
import type { CatalogSku, FinanceLedgerEntry, Settlement } from "../types/admin"

defineProps<{
  settlements: Settlement[]
}>()

type FinanceView = "withdrawals" | "settlements" | "fees" | "ledger"
const view = ref<FinanceView>("withdrawals")
const skus = ref<CatalogSku[]>([])
const ledger = ref<FinanceLedgerEntry[]>([])
const feeError = ref("")
const ledgerError = ref("")
const ledgerBizType = ref("")
const ledgerEntryType = ref("")
const ledgerUserId = ref("")
const loadingFees = ref(false)
const loadingLedger = ref(false)
const busySkuId = ref("")

function money(value: number) {
  return `¥${(value / 100).toFixed(2)}`
}

function feePercent(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

async function loadFeeSettings() {
  loadingFees.value = true
  feeError.value = ""
  try {
    skus.value = await adminRequest<CatalogSku[]>("/admin/catalog/skus")
  } catch (cause) {
    feeError.value = cause instanceof Error ? cause.message : "抽成设置加载失败"
  } finally {
    loadingFees.value = false
  }
}

async function loadLedger() {
  loadingLedger.value = true
  ledgerError.value = ""
  try {
    const params = new URLSearchParams()
    if (ledgerBizType.value.trim()) params.set("biz_type", ledgerBizType.value.trim())
    if (ledgerEntryType.value.trim()) params.set("entry_type", ledgerEntryType.value.trim())
    if (ledgerUserId.value.trim()) params.set("user_id", ledgerUserId.value.trim())
    const suffix = params.toString() ? `?${params}` : ""
    ledger.value = await adminRequest<FinanceLedgerEntry[]>(`/admin/ledger${suffix}`)
  } catch (cause) {
    ledgerError.value = cause instanceof Error ? cause.message : "财务流水加载失败"
  } finally {
    loadingLedger.value = false
  }
}

async function updateFeeRate(sku: CatalogSku) {
  const input = window.prompt("请输入平台抽成比例，例如 20 表示 20%", (sku.platformFeeRate * 100).toFixed(2))
  if (input === null) return
  const percent = Number(input.trim())
  if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
    feeError.value = "平台抽成比例必须在 0 到 100 之间"
    return
  }
  busySkuId.value = sku.id
  feeError.value = ""
  try {
    await adminRequest(`/admin/catalog/skus/${sku.id}`, {
      method: "PATCH",
      body: { platform_fee_rate: Number((percent / 100).toFixed(4)) }
    })
    await loadFeeSettings()
  } catch (cause) {
    feeError.value = cause instanceof Error ? cause.message : "平台抽成保存失败"
  } finally {
    busySkuId.value = ""
  }
}

onMounted(() => {
  void loadFeeSettings()
  void loadLedger()
})
</script>

<template>
  <div class="subnav">
    <button
      :class="{ active: view === 'withdrawals' }"
      @click="view = 'withdrawals'"
    >
      提现
    </button>
    <button
      :class="{ active: view === 'settlements' }"
      @click="view = 'settlements'"
    >
      结算
    </button>
    <button
      :class="{ active: view === 'fees' }"
      @click="view = 'fees'"
    >
      平台抽成
    </button>
    <button
      :class="{ active: view === 'ledger' }"
      @click="view = 'ledger'"
    >
      财务流水
    </button>
  </div>

  <WithdrawalsPanel v-if="view === 'withdrawals'" />

  <section v-else-if="view === 'settlements'" class="panel">
    <div class="panel-head">
      <div>
        <h2>结算</h2>
        <p>Settlement 与 Ledger 保留为资金审计事实，不作为独立产品入口。</p>
      </div>
      <span class="count">{{ settlements.length }} 笔</span>
    </div>
    <div class="table settlements">
      <div class="tr th">
        <span>结算 ID</span>
        <span>状态</span>
        <span>订单金额</span>
        <span>陪玩收入</span>
        <span>平台服务费</span>
      </div>
      <div v-for="item in settlements" :key="item.id" class="tr">
        <span class="identity">
          <b>{{ item.id.slice(0, 12) }}</b>
          <small>{{ item.orderId.slice(0, 8) }}</small>
        </span>
        <span><em class="badge green">{{ item.status }}</em></span>
        <span>{{ money(item.grossAmount) }}</span>
        <span>{{ money(item.playerAmount) }}</span>
        <span>{{ money(item.platformFee) }}</span>
      </div>
    </div>
  </section>

  <section v-else-if="view === 'fees'" class="panel">
    <div class="panel-head">
      <div>
        <h2>平台抽成设置</h2>
        <p>按服务套餐配置平台服务费比例，只影响新创建订单，历史订单不回改。</p>
      </div>
      <button class="refresh" type="button" @click="loadFeeSettings">刷新</button>
    </div>
    <div v-if="feeError" class="alert">{{ feeError }}</div>
    <div v-if="loadingFees" class="loading">正在加载抽成设置...</div>
    <div v-else class="table fee-table">
      <div class="tr th">
        <span>服务套餐</span>
        <span>游戏</span>
        <span>价格</span>
        <span>平台抽成</span>
        <span>操作</span>
      </div>
      <div v-for="sku in skus" :key="sku.id" class="tr">
        <span class="identity">
          <b>{{ sku.name }}</b>
          <small>{{ sku.durationMinutes }} 分钟 · {{ sku.status }}</small>
        </span>
        <span>{{ sku.gameName }}</span>
        <span>{{ money(sku.price) }}</span>
        <span><em class="badge">{{ feePercent(sku.platformFeeRate) }}</em></span>
        <span class="actions">
          <button class="approve" type="button" :disabled="busySkuId === sku.id" @click="updateFeeRate(sku)">
            调整抽成
          </button>
        </span>
      </div>
    </div>
  </section>

  <section v-else class="panel">
    <div class="panel-head">
      <div>
        <h2>财务流水明细</h2>
        <p>展示钱包 Ledger 事实记录，只读留痕，用于对账和资金审计。</p>
      </div>
      <span class="count">{{ ledger.length }} 条</span>
    </div>

    <div class="filter-bar">
      <input v-model="ledgerBizType" placeholder="业务类型，例如 SETTLEMENT" />
      <input v-model="ledgerEntryType" placeholder="流水类型，例如 PLAYER_INCOME" />
      <input v-model="ledgerUserId" placeholder="用户 ID" />
      <button class="refresh" type="button" @click="loadLedger">查询</button>
    </div>
    <div v-if="ledgerError" class="alert">{{ ledgerError }}</div>
    <div v-if="loadingLedger" class="loading">正在加载财务流水...</div>
    <div v-else class="table ledger-table">
      <div class="tr th">
        <span>用户 / 账户</span>
        <span>业务</span>
        <span>流水类型</span>
        <span>金额 / 余额</span>
        <span>时间</span>
      </div>
      <div v-for="item in ledger" :key="item.id" class="tr">
        <span class="identity">
          <b>{{ item.nickname || item.userId.slice(0, 8) }}</b>
          <small>{{ item.userId.slice(0, 8) }} · {{ item.accountId.slice(0, 8) }}</small>
        </span>
        <span class="identity">
          <b>{{ item.bizType }}</b>
          <small>{{ item.bizId || "-" }}</small>
        </span>
        <span><em class="badge">{{ item.entryType }}</em></span>
        <span class="identity">
          <b>{{ money(item.amount) }}</b>
          <small>余额 {{ money(item.balanceAfter) }}</small>
        </span>
        <span>{{ new Date(item.createdAt).toLocaleString() }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.filter-bar{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;margin-bottom:18px}
.filter-bar input{height:40px;padding:0 12px;border-radius:12px}
.actions button:disabled{cursor:not-allowed;opacity:.55}
@media(max-width:1200px){.filter-bar{grid-template-columns:1fr 1fr}.filter-bar .refresh{height:40px}}
</style>
