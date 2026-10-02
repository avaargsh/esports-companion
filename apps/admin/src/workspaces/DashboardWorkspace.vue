<script setup lang="ts">
import { computed } from "vue"

import OperationsQueuePanel from "../components/OperationsQueuePanel.vue"
import type {
  Order,
  Player,
  Settlement
} from "../types/admin"

const props = defineProps<{
  orders: Order[]
  players: Player[]
  settlements: Settlement[]
}>()

const pendingPlayers = computed(() =>
  props.players.filter(item => item.verificationStatus === "PENDING")
)

const gmv = computed(() =>
  props.orders.reduce((sum, item) => sum + item.totalAmount, 0)
)

const platformRevenue = computed(() =>
  props.settlements.reduce((sum, item) => sum + item.platformFee, 0)
)
</script>

<template>
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
