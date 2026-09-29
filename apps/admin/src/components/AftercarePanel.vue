<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"

type Dispute = {
  id: string
  order_id: string
  status: string
  opened_by_user_id: string
  opened_by_role: string
  reason_code: string
  description: string
  held_amount: number
  resolution: string | null
  resolved_by_user_id: string | null
  resolved_at: string | null
  created_at: string
}

type Refund = {
  id: string
  order_id: string
  dispute_id: string
  amount: number
  status: string
  provider: string
  out_refund_no: string | null
  provider_refund_id: string | null
  completed_at: string | null
}

const disputes = ref<Dispute[]>([])
const refunds = ref<Refund[]>([])
const loading = ref(true)
const busyId = ref("")
const error = ref("")

const openDisputes = computed(() =>
  disputes.value.filter((item) => item.status === "OPEN")
)

const inflightRefunds = computed(() =>
  refunds.value.filter((item) => item.status !== "COMPLETED")
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [nextDisputes, nextRefunds] = await Promise.all([
      adminRequest<Dispute[]>("/admin/disputes"),
      adminRequest<Refund[]>("/admin/refunds")
    ])
    disputes.value = nextDisputes
    refunds.value = nextRefunds
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "售后数据加载失败"
  } finally {
    loading.value = false
  }
}

async function resolveDispute(dispute: Dispute, action: "refund" | "release") {
  if (busyId.value) return
  busyId.value = dispute.id
  error.value = ""
  try {
    await adminRequest(`/admin/disputes/${dispute.id}/${action}`, {
      method: "POST"
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "争议处理失败"
  } finally {
    busyId.value = ""
  }
}

async function reconcile(refund: Refund) {
  if (busyId.value) return
  busyId.value = refund.id
  error.value = ""
  try {
    await adminRequest(`/admin/refunds/${refund.id}/reconcile`, {
      method: "POST"
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "退款对账失败"
  } finally {
    busyId.value = ""
  }
}

async function completeManual(refund: Refund) {
  if (busyId.value) return
  busyId.value = refund.id
  error.value = ""
  try {
    await adminRequest(`/admin/refunds/${refund.id}/complete`, {
      method: "POST",
      body: {
        provider_refund_id: `manual:${refund.id}`
      }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "人工退款完成失败"
  } finally {
    busyId.value = ""
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="metric-strip">
      <article>
        <span>待裁决争议</span>
        <strong>{{ openDisputes.length }}</strong>
      </article>
      <article>
        <span>退款处理中</span>
        <strong>{{ inflightRefunds.length }}</strong>
      </article>
      <article>
        <span>退款完成</span>
        <strong>{{ refunds.filter(item => item.status === "COMPLETED").length }}</strong>
      </article>
    </div>

    <div v-if="error" class="aftercare-alert">{{ error }}</div>
    <div v-if="loading" class="aftercare-loading">正在同步争议与退款状态...</div>

    <template v-else>
      <section class="aftercare-panel">
        <div class="panel-head">
          <div>
            <h2>争议裁决</h2>
            <p>DISPUTED 会冻结正常结算；运营只选择退款或继续向服务方结算。</p>
          </div>
          <button class="refresh-small" @click="load">刷新</button>
        </div>

        <div v-if="disputes.length === 0" class="empty">暂无争议</div>
        <div v-else class="aftercare-table dispute-table">
          <div class="aftercare-row th">
            <span>订单 / 原因</span>
            <span>发起方</span>
            <span>冻结金额</span>
            <span>状态</span>
            <span>运营动作</span>
          </div>
          <div v-for="item in disputes" :key="item.id" class="aftercare-row">
            <span class="identity">
              <b>{{ item.order_id.slice(0, 12) }}</b>
              <small>{{ item.reason_code }} · {{ item.description || "无补充说明" }}</small>
            </span>
            <span>{{ item.opened_by_role }}</span>
            <span>¥{{ (item.held_amount / 100).toFixed(2) }}</span>
            <span>
              <em class="status-badge" :class="item.status.toLowerCase()">
                {{ item.status }}
              </em>
              <small v-if="item.resolution" class="resolution">{{ item.resolution }}</small>
            </span>
            <span class="row-actions">
              <template v-if="item.status === 'OPEN'">
                <button
                  class="danger"
                  :disabled="Boolean(busyId)"
                  @click="resolveDispute(item, 'refund')"
                >
                  批准退款
                </button>
                <button
                  class="neutral"
                  :disabled="Boolean(busyId)"
                  @click="resolveDispute(item, 'release')"
                >
                  继续结算
                </button>
              </template>
              <small v-else>已进入 {{ item.resolution || item.status }}</small>
            </span>
          </div>
        </div>
      </section>

      <section class="aftercare-panel">
        <div class="panel-head">
          <div>
            <h2>退款执行与对账</h2>
            <p>微信退款只能由回调或签名查询确认；人工完成仅用于 MANUAL Provider。</p>
          </div>
          <span class="count">{{ refunds.length }} 笔</span>
        </div>

        <div v-if="refunds.length === 0" class="empty">暂无退款</div>
        <div v-else class="aftercare-table refund-table">
          <div class="aftercare-row th">
            <span>退款 / 订单</span>
            <span>Provider</span>
            <span>金额</span>
            <span>状态</span>
            <span>恢复动作</span>
          </div>
          <div v-for="item in refunds" :key="item.id" class="aftercare-row">
            <span class="identity">
              <b>{{ item.id.slice(0, 12) }}</b>
              <small>{{ item.out_refund_no || item.order_id.slice(0, 12) }}</small>
            </span>
            <span>{{ item.provider }}</span>
            <span>¥{{ (item.amount / 100).toFixed(2) }}</span>
            <span>
              <em class="status-badge" :class="item.status.toLowerCase()">
                {{ item.status }}
              </em>
              <small v-if="item.provider_refund_id" class="resolution">
                {{ item.provider_refund_id }}
              </small>
            </span>
            <span class="row-actions">
              <button
                v-if="item.provider === 'WECHAT' && item.status !== 'COMPLETED'"
                class="approve"
                :disabled="Boolean(busyId)"
                @click="reconcile(item)"
              >
                微信对账
              </button>
              <button
                v-else-if="item.provider === 'MANUAL' && item.status !== 'COMPLETED'"
                class="neutral"
                :disabled="Boolean(busyId)"
                @click="completeManual(item)"
              >
                标记人工退款完成
              </button>
              <small v-else>已完成</small>
            </span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.metric-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.metric-strip article { padding: 20px 22px; border: 1px solid #ecebf1; border-radius: 18px; background: #fff; }
.metric-strip span { color: #92929d; font-size: 11px; }
.metric-strip strong { display: block; margin-top: 10px; font-size: 28px; }
.aftercare-panel { margin-top: 22px; padding: 26px; border: 1px solid #ecebf1; border-radius: 22px; background: #fff; box-shadow: 0 16px 45px rgba(30,23,70,.035); }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 22px; }
.panel-head h2 { margin: 0; font-size: 18px; }
.panel-head p { margin: 7px 0 0; color: #92929d; font-size: 12px; }
.refresh-small { border: 1px solid #e4e3eb; padding: 8px 12px; border-radius: 10px; background: #fff; cursor: pointer; }
.aftercare-table { width: 100%; }
.aftercare-row { display: grid; grid-template-columns: 1.7fr .7fr .7fr 1fr 1.4fr; align-items: center; gap: 14px; min-height: 70px; padding: 12px 8px; border-top: 1px solid #f0eff4; font-size: 12px; }
.aftercare-row.th { min-height: 40px; border: 0; color: #92929d; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.identity b, .identity small, .resolution { display: block; }
.identity small { max-width: 320px; margin-top: 5px; overflow: hidden; color: #a6a5af; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
.resolution { margin-top: 5px; color: #92929d; font-size: 9px; }
.status-badge { display: inline-block; padding: 6px 9px; border-radius: 999px; background: #f1efff; color: #6c5ce7; font-style: normal; font-size: 10px; }
.status-badge.completed, .status-badge.resolved { background: #eafbf2; color: #198754; }
.status-badge.open, .status-badge.pending, .status-badge.processing, .status-badge.submitting { background: #fff7dd; color: #9b7410; }
.status-badge.closed, .status-badge.abnormal { background: #fff0f0; color: #c63d3d; }
.row-actions { display: flex; flex-wrap: wrap; gap: 7px; }
.row-actions button { border: 0; padding: 8px 10px; border-radius: 9px; cursor: pointer; font-size: 11px; }
.row-actions button:disabled { opacity: .45; cursor: default; }
.approve { background: #6c5ce7; color: #fff; }
.danger { background: #fff0f0; color: #c63d3d; }
.neutral { background: #f2f1f5; color: #686872; }
.aftercare-alert { margin-bottom: 18px; padding: 14px 16px; border-radius: 13px; background: #fff0f0; color: #c63d3d; font-size: 12px; }
.aftercare-loading, .empty { padding: 50px; color: #92929d; text-align: center; font-size: 12px; }
.count { padding: 8px 12px; border-radius: 999px; background: #f2f1f7; color: #686872; font-size: 11px; }
</style>
