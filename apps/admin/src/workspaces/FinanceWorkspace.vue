<script setup lang="ts">
import { ref } from "vue"

import WithdrawalsPanel from "../components/WithdrawalsPanel.vue"
import type { Settlement } from "../types/admin"

defineProps<{
  settlements: Settlement[]
}>()

type FinanceView = "withdrawals" | "settlements"
const view = ref<FinanceView>("withdrawals")
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
  </div>

  <WithdrawalsPanel v-if="view === 'withdrawals'" />

  <section v-else class="panel">
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
        <span>¥{{ (item.grossAmount / 100).toFixed(2) }}</span>
        <span>¥{{ (item.playerAmount / 100).toFixed(2) }}</span>
        <span>¥{{ (item.platformFee / 100).toFixed(2) }}</span>
      </div>
    </div>
  </section>
</template>
