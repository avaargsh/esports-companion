<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { api, type DemoIdentities } from "./api"

type Player = {
  id: string
  userId: string
  displayName: string
  verificationStatus: string
  serviceStatus: string
  rating: number
  orderCount: number
}

type Order = {
  id: string
  orderNo: string
  userId: string
  status: string
  totalAmount: number
  version: number
  createdAt: string
}

type Settlement = {
  id: string
  orderId: string
  playerId: string
  grossAmount: number
  playerAmount: number
  platformFee: number
  status: string
}

const tab = ref<"dashboard" | "players" | "orders" | "settlements">("dashboard")
const adminId = ref("")
const players = ref<Player[]>([])
const orders = ref<Order[]>([])
const settlements = ref<Settlement[]>([])
const loading = ref(true)
const error = ref("")

const pendingPlayers = computed(() =>
  players.value.filter(item => item.verificationStatus === "PENDING")
)
const gmv = computed(() =>
  settlements.value.reduce((sum, item) => sum + item.grossAmount, 0)
)
const platformRevenue = computed(() =>
  settlements.value.reduce((sum, item) => sum + item.platformFee, 0)
)

function money(value: number) {
  return "¥" + (value / 100).toFixed(2)
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const demo = await api<DemoIdentities>("/dev/demo-identities")
    if (!demo.admin) throw new Error("DEMO_ADMIN_NOT_FOUND")
    adminId.value = demo.admin.userId
    const [playerRows, orderRows, settlementRows] = await Promise.all([
      api<Player[]>("/admin/players", { adminId: adminId.value }),
      api<Order[]>("/admin/orders", { adminId: adminId.value }),
      api<Settlement[]>("/admin/settlements", { adminId: adminId.value })
    ])
    players.value = playerRows
    orders.value = orderRows
    settlements.value = settlementRows
  } catch (e) {
    error.value = e instanceof Error ? e.message : "LOAD_FAILED"
  } finally {
    loading.value = false
  }
}

async function reviewPlayer(player: Player, action: "approve" | "reject") {
  try {
    await api(`/admin/players/${player.id}/${action}`, {
      method: "POST",
      adminId: adminId.value
    })
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : "ACTION_FAILED"
  }
}

onMounted(load)
</script>

<template>
  <div class="shell">
    <aside>
      <div class="brand">
        <div class="logo">EC</div>
        <div>
          <strong>Esports Companion</strong>
          <small>Operations Console</small>
        </div>
      </div>

      <nav>
        <button :class="{ active: tab === 'dashboard' }" @click="tab = 'dashboard'">概览</button>
        <button :class="{ active: tab === 'players' }" @click="tab = 'players'">
          陪玩审核 <span v-if="pendingPlayers.length">{{ pendingPlayers.length }}</span>
        </button>
        <button :class="{ active: tab === 'orders' }" @click="tab = 'orders'">订单管理</button>
        <button :class="{ active: tab === 'settlements' }" @click="tab = 'settlements'">结算</button>
      </nav>

      <div class="side-foot">
        <div class="online-dot"></div>
        Demo Admin
      </div>
    </aside>

    <main>
      <header>
        <div>
          <h1>
            {{
              tab === "dashboard"
                ? "Marketplace Overview"
                : tab === "players"
                  ? "Player Review"
                  : tab === "orders"
                    ? "Order Management"
                    : "Settlement"
            }}
          </h1>
          <p>v0.1 · Modular Monolith · PostgreSQL truth</p>
        </div>
        <button class="refresh" @click="load">刷新</button>
      </header>

      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="loading" class="loading">正在同步平台状态...</div>

      <template v-else-if="tab === 'dashboard'">
        <section class="metric-grid">
          <article>
            <span>订单总数</span>
            <strong>{{ orders.length }}</strong>
            <small>最近 100 条</small>
          </article>
          <article>
            <span>GMV</span>
            <strong>{{ money(gmv) }}</strong>
            <small>已结算口径</small>
          </article>
          <article>
            <span>平台收入</span>
            <strong>{{ money(platformRevenue) }}</strong>
            <small>Ledger-backed</small>
          </article>
          <article>
            <span>待审核陪玩</span>
            <strong>{{ pendingPlayers.length }}</strong>
            <small>需要运营处理</small>
          </article>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Marketplace Health</h2>
              <p>Golden Slice 当前运行态</p>
            </div>
            <span class="badge green">● API Ready</span>
          </div>
          <div class="flow">
            <span>Create</span><i>→</i><span>Pay</span><i>→</i><span>Matching</span><i>→</i>
            <span>Claim</span><i>→</i><span>Service</span><i>→</i><span>Settle</span>
          </div>
        </section>
      </template>

      <section v-else-if="tab === 'players'" class="panel">
        <div class="panel-head">
          <div><h2>陪玩审核</h2><p>申请状态与服务状态分离</p></div>
          <span class="badge">{{ players.length }} profiles</span>
        </div>
        <table>
          <thead><tr><th>陪玩</th><th>审核状态</th><th>服务状态</th><th>评分</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="player in players" :key="player.id">
              <td><b>{{ player.displayName }}</b><small>{{ player.id.slice(0, 8) }}</small></td>
              <td><span class="status-chip">{{ player.verificationStatus }}</span></td>
              <td>{{ player.serviceStatus }}</td>
              <td>{{ player.rating.toFixed(1) }}</td>
              <td>
                <div v-if="player.verificationStatus === 'PENDING'" class="row-actions">
                  <button class="approve" @click="reviewPlayer(player, 'approve')">通过</button>
                  <button class="reject" @click="reviewPlayer(player, 'reject')">拒绝</button>
                </div>
                <span v-else class="muted">已处理</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-else-if="tab === 'orders'" class="panel">
        <div class="panel-head">
          <div><h2>订单查询</h2><p>PostgreSQL durable state</p></div>
          <span class="badge">{{ orders.length }} orders</span>
        </div>
        <table>
          <thead><tr><th>订单号</th><th>状态</th><th>金额</th><th>版本</th><th>创建时间</th></tr></thead>
          <tbody>
            <tr v-for="order in orders" :key="order.id">
              <td><b>{{ order.orderNo }}</b><small>{{ order.id.slice(0, 8) }}</small></td>
              <td><span class="status-chip">{{ order.status }}</span></td>
              <td>{{ money(order.totalAmount) }}</td>
              <td>v{{ order.version }}</td>
              <td>{{ new Date(order.createdAt).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-else class="panel">
        <div class="panel-head">
          <div><h2>结算记录</h2><p>Provider income + Platform fee</p></div>
          <span class="badge">{{ settlements.length }} settlements</span>
        </div>
        <table>
          <thead><tr><th>订单</th><th>总额</th><th>陪玩收入</th><th>平台收入</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="item in settlements" :key="item.id">
              <td><b>{{ item.orderId.slice(0, 12) }}</b></td>
              <td>{{ money(item.grossAmount) }}</td>
              <td>{{ money(item.playerAmount) }}</td>
              <td>{{ money(item.platformFee) }}</td>
              <td><span class="status-chip">{{ item.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
</template>
