<script setup lang="ts">
import { ref } from "vue"

import AftercarePanel from "../components/AftercarePanel.vue"
import type { Order } from "../types/admin"

defineProps<{
  orders: Order[]
}>()

const emit = defineEmits<{
  "open-evidence": [orderId: string]
}>()

type OrderView = "orders" | "aftercare"
const view = ref<OrderView>("orders")
</script>

<template>
  <div class="subnav">
    <button
      :class="{ active: view === 'orders' }"
      @click="view = 'orders'"
    >
      订单列表
    </button>
    <button
      :class="{ active: view === 'aftercare' }"
      @click="view = 'aftercare'"
    >
      售后 / 退款
    </button>
  </div>

  <section v-if="view === 'orders'" class="panel">
    <div class="panel-head">
      <div>
        <h2>订单</h2>
        <p>订单状态、聊天与审计事实统一从订单进入。</p>
      </div>
      <span class="count">{{ orders.length }} 单</span>
    </div>
    <div class="table orders">
      <div class="tr th">
        <span>订单号</span>
        <span>状态</span>
        <span>金额</span>
        <span>版本</span>
        <span>创建时间</span>
      </div>
      <div v-for="order in orders" :key="order.id" class="tr">
        <span class="identity">
          <b>{{ order.orderNo }}</b>
          <small>{{ order.id.slice(0, 8) }}</small>
        </span>
        <span><em class="badge purple">{{ order.status }}</em></span>
        <span>¥{{ (order.totalAmount / 100).toFixed(2) }}</span>
        <span>v{{ order.version }}</span>
        <span class="order-actions">
          <small>{{ new Date(order.createdAt).toLocaleString() }}</small>
          <button
            class="evidence-button"
            @click="emit('open-evidence', order.id)"
          >
            查看详情
          </button>
        </span>
      </div>
    </div>
  </section>

  <AftercarePanel v-else />
</template>
