<script setup lang="ts">
import { computed, ref, watch } from "vue"

import { adminRequest } from "../api"

type ServicePlayer = {
  id: string
  display_name: string
  rating: number
  service_status: string
  status_code?: string
  service_status_code?: string
  binding: string
  assigned_by?: string | null
}

type OrderDetail = {
  id: string
  order_no: string
  user_id: string
  status: string
  status_code?: string
  quantity: number
  unit_price: number
  total_amount: number
  player_amount: number
  platform_fee: number
  version: number
  service_player?: ServicePlayer | null
}

type OrderEvent = {
  id: string
  event_type: string
  from_status?: string | null
  from_status_code?: string | null
  to_status?: string | null
  to_status_code?: string | null
  actor_type: string
  created_at: string
}

type OrderMessage = {
  id: string
  sender_role: string
  content: string
  created_at: string
}

const props = defineProps<{ orderId: string }>()
const emit = defineEmits<{ close: [] }>()

const order = ref<OrderDetail | null>(null)
const events = ref<OrderEvent[]>([])
const messages = ref<OrderMessage[]>([])
const loading = ref(false)
const error = ref("")

const latestEvent = computed(() => events.value[events.value.length - 1])
const hasChat = computed(() => messages.value.length > 0)

const eventLabels: Record<string,string> = {
  ORDER_CREATED: "订单创建",
  PAYMENT_SUCCESS: "支付成功",
  ORDER_ENTERED_MATCHING: "进入匹配",
  ORDER_CLAIMED: "陪玩接单",
  ORDER_ASSIGNED: "指定 / 分配陪玩",
  SERVICE_STARTED: "开始服务",
  FINISH_REQUESTED: "陪玩申请完成",
  USER_CONFIRMED_FINISH: "用户确认完成",
  AUTO_CONFIRMED_FINISH: "系统自动确认",
  ORDER_SETTLED: "订单结算",
  DISPUTE_OPENED: "发起争议",
  REFUND_COMPLETED: "退款完成"
}

function money(value: number | undefined) {
  return "¥" + (((value ?? 0) / 100).toFixed(2))
}

function time(value: string | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function eventTitle(event: OrderEvent) {
  return eventLabels[event.event_type] || event.event_type
}

async function load() {
  if (!props.orderId) return
  loading.value = true
  error.value = ""
  try {
    const [nextOrder, nextEvents, nextMessages] = await Promise.all([
      adminRequest<OrderDetail>("/orders/" + props.orderId),
      adminRequest<OrderEvent[]>("/orders/" + props.orderId + "/events"),
      adminRequest<OrderMessage[]>("/orders/" + props.orderId + "/messages?limit=200")
    ])
    order.value = nextOrder
    events.value = nextEvents
    messages.value = nextMessages
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "订单事实加载失败"
  } finally {
    loading.value = false
  }
}

watch(() => props.orderId, () => { void load() }, { immediate: true })
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <aside class="drawer">
      <header class="drawer-head">
        <div>
          <span class="eyebrow">ORDER EVIDENCE</span>
          <h2>{{ order?.order_no || orderId.slice(0, 12) }}</h2>
          <p>只读事实视图：订单状态、资金拆分、OrderEvent 与订单聊天。</p>
        </div>
        <button class="close" @click="emit('close')">关闭</button>
      </header>

      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="loading" class="loading">正在加载订单事实…</div>

      <template v-else-if="order">
        <section class="summary">
          <article>
            <span>当前状态</span>
            <strong>{{ order.status }}</strong>
            <small>v{{ order.version }} · 最新事件 {{ latestEvent?.event_type || "—" }}</small>
          </article>
          <article>
            <span>用户实付</span>
            <strong>{{ money(order.total_amount) }}</strong>
            <small>{{ money(order.unit_price) }} × {{ order.quantity }}</small>
          </article>
          <article>
            <span>陪玩应得</span>
            <strong>{{ money(order.player_amount) }}</strong>
            <small>平台费 {{ money(order.platform_fee) }}</small>
          </article>
        </section>

        <section class="facts">
          <div><span>用户</span><b>{{ order.user_id }}</b></div>
          <div>
            <span>服务陪玩</span>
            <b v-if="order.service_player">
              {{ order.service_player.display_name }}
              · {{ order.service_player.binding }}
              · {{ order.service_player.service_status }}
            </b>
            <b v-else>尚未绑定</b>
          </div>
        </section>

        <section class="block">
          <div class="block-head">
            <div>
              <h3>履约 Evidence</h3>
              <p>来自 append-only OrderEvent；运营台不修改该时间线。</p>
            </div>
            <span>{{ events.length }} 条</span>
          </div>
          <div v-if="!events.length" class="empty">暂无事件</div>
          <div v-for="(event,index) in events" :key="event.id" class="event">
            <div class="track">
              <i :class="{ latest:index === events.length - 1 }"></i>
              <span v-if="index < events.length - 1"></span>
            </div>
            <div class="event-main">
              <div class="event-title">
                <b>{{ eventTitle(event) }}</b>
                <time>{{ time(event.created_at) }}</time>
              </div>
              <small>
                {{ event.actor_type }}
                <template v-if="event.from_status || event.to_status">
                  · {{ event.from_status || "∅" }} → {{ event.to_status || "∅" }}
                </template>
              </small>
            </div>
          </div>
        </section>

        <section class="block">
          <div class="block-head">
            <div>
              <h3>订单聊天</h3>
              <p>PLATFORM 只读；用于售后取证，不允许从运营台冒充用户或陪玩发送。</p>
            </div>
            <span>{{ messages.length }} 条</span>
          </div>
          <div v-if="!hasChat" class="empty">该订单没有聊天记录</div>
          <div v-for="message in messages" :key="message.id" class="message">
            <div class="message-meta">
              <b>{{ message.sender_role === "USER" ? "用户" : "陪玩" }}</b>
              <time>{{ time(message.created_at) }}</time>
            </div>
            <p>{{ message.content }}</p>
          </div>
        </section>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.backdrop { position:fixed; inset:0; z-index:50; background:rgba(15,15,21,.38); display:flex; justify-content:flex-end; }
.drawer { width:min(760px,72vw); height:100vh; overflow:auto; padding:28px; background:#f7f7fa; box-shadow:-24px 0 70px rgba(20,18,40,.14); }
.drawer-head { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; }
.eyebrow { color:#6c5ce7; font-size:10px; font-weight:900; letter-spacing:1.8px; }
h2 { margin:8px 0 0; font-size:25px; }
.drawer-head p,.block-head p { margin:6px 0 0; color:#8d8d98; font-size:11px; line-height:1.5; }
.close { border:1px solid #dfdee7; border-radius:10px; padding:8px 12px; background:#fff; color:#666672; cursor:pointer; }
.error { margin-top:18px; padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.loading,.empty { padding:34px 18px; color:#9999a4; text-align:center; font-size:12px; }
.summary { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:22px; }
.summary article { padding:18px; border:1px solid #ecebf1; border-radius:16px; background:#fff; }
.summary span,.summary small { display:block; color:#92929d; font-size:10px; }
.summary strong { display:block; margin:9px 0 5px; font-size:17px; overflow-wrap:anywhere; }
.facts { margin-top:12px; padding:16px 18px; border:1px solid #ecebf1; border-radius:16px; background:#fff; }
.facts div { display:grid; grid-template-columns:90px 1fr; gap:12px; padding:8px 0; font-size:11px; }
.facts span { color:#92929d; }
.facts b { overflow-wrap:anywhere; font-weight:650; }
.block { margin-top:14px; padding:20px; border:1px solid #ecebf1; border-radius:18px; background:#fff; }
.block-head { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:14px; }
.block-head h3 { margin:0; font-size:15px; }
.block-head>span { padding:5px 8px; border-radius:999px; background:#f2f1f7; color:#777783; font-size:9px; }
.event { display:flex; gap:12px; min-height:58px; }
.track { width:12px; display:flex; align-items:center; flex-direction:column; }
.track i { width:9px; height:9px; flex:none; border-radius:50%; background:#bbb9c6; }
.track i.latest { background:#6c5ce7; box-shadow:0 0 0 4px rgba(108,92,231,.10); }
.track span { width:1px; flex:1; margin-top:5px; background:#e5e4ec; }
.event-main { flex:1; padding-bottom:14px; }
.event-title,.message-meta { display:flex; justify-content:space-between; gap:14px; align-items:flex-start; }
.event-title b { font-size:11px; }
time { color:#aaaab4; font-size:9px; }
.event-main small { display:block; margin-top:5px; color:#8f8f9a; font-size:9px; }
.message { padding:12px 0; border-top:1px solid #f0eff4; }
.message:first-of-type { border-top:0; }
.message-meta b { color:#6c5ce7; font-size:10px; }
.message p { margin:7px 0 0; color:#363640; font-size:11px; line-height:1.6; white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
