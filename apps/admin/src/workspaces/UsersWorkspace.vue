<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import type { AdminUser, ConsumptionRecord } from "../types/admin"

type UserView = "players" | "blacklist"

const view = ref<UserView>("players")
const users = ref<AdminUser[]>([])
const records = ref<ConsumptionRecord[]>([])
const selected = ref<AdminUser | null>(null)
const loading = ref(false)
const recordsLoading = ref(false)
const error = ref("")

const filteredUsers = computed(() =>
  view.value === "blacklist"
    ? users.value.filter(item => item.statusCode === "BLOCKED")
    : users.value
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    users.value = await adminRequest<AdminUser[]>("/admin/users")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "用户加载失败"
  } finally {
    loading.value = false
  }
}

async function openRecords(user: AdminUser) {
  selected.value = user
  records.value = []
  recordsLoading.value = true
  try {
    records.value = await adminRequest<ConsumptionRecord[]>(`/admin/users/${user.id}/consumption-records`)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "消费记录加载失败"
  } finally {
    recordsLoading.value = false
  }
}

async function updateStatus(user: AdminUser, status: "ACTIVE" | "BLOCKED") {
  const reason = status === "BLOCKED"
    ? window.prompt("请输入拉黑原因", "风控处理")
    : window.prompt("请输入恢复原因", "解除风控")
  if (!reason?.trim()) return
  try {
    await adminRequest(`/admin/users/${user.id}/status`, {
      method: "PATCH",
      body: { status, reason: reason.trim() }
    })
    await load()
    if (selected.value?.id === user.id) selected.value = null
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "状态更新失败"
  }
}

onMounted(load)
</script>

<template>
  <div class="subnav">
    <button :class="{ active: view === 'players' }" @click="view = 'players'">玩家列表</button>
    <button :class="{ active: view === 'blacklist' }" @click="view = 'blacklist'">黑名单管理</button>
  </div>

  <section class="panel">
    <div class="panel-head">
      <div>
        <h2>{{ view === "blacklist" ? "黑名单管理" : "玩家列表" }}</h2>
        <p>展示真实账号、余额、消费次数与风控状态。</p>
      </div>
      <button class="refresh" @click="load">刷新</button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading" class="loading">正在读取用户数据...</div>
    <div v-else class="table users-table">
      <div class="tr th">
        <span>用户</span>
        <span>手机号</span>
        <span>身份</span>
        <span>消费</span>
        <span>状态</span>
        <span>操作</span>
      </div>
      <div v-for="user in filteredUsers" :key="user.id" class="tr">
        <span class="identity">
          <b>{{ user.nickname || "未命名用户" }}</b>
          <small>{{ user.id.slice(0, 8) }} · {{ user.openid || "无 openid" }}</small>
        </span>
        <span>{{ user.phone || "未绑定" }}</span>
        <span>{{ user.role }}</span>
        <span>
          <b>¥{{ (user.totalSpent / 100).toFixed(2) }}</b>
          <small>{{ user.orderCount }} 单</small>
        </span>
        <span><em class="badge" :class="{ danger: user.statusCode === 'BLOCKED' }">{{ user.status }}</em></span>
        <span class="actions">
          <button class="approve" @click="openRecords(user)">消费记录</button>
          <button v-if="user.statusCode !== 'BLOCKED'" class="reject" @click="updateStatus(user, 'BLOCKED')">拉黑</button>
          <button v-else class="approve" @click="updateStatus(user, 'ACTIVE')">恢复</button>
        </span>
      </div>
    </div>
  </section>

  <section v-if="selected" class="panel detail-panel">
    <div class="panel-head">
      <div>
        <h2>{{ selected.nickname || selected.id.slice(0, 8) }} 的消费记录</h2>
        <p>订单支付、金额和结算字段会保留为财务追踪依据。</p>
      </div>
      <button class="refresh" @click="selected = null">关闭</button>
    </div>
    <div v-if="recordsLoading" class="loading">正在读取消费记录...</div>
    <div v-else class="table records-table">
      <div class="tr th">
        <span>订单</span>
        <span>状态</span>
        <span>支付金额</span>
        <span>平台服务费</span>
        <span>陪玩收入</span>
        <span>时间</span>
      </div>
      <div v-for="item in records" :key="item.id" class="tr">
        <span class="identity"><b>{{ item.orderNo }}</b><small>{{ item.id.slice(0, 8) }}</small></span>
        <span><em class="badge">{{ item.status }}</em></span>
        <span>¥{{ (item.amount / 100).toFixed(2) }}</span>
        <span>¥{{ (item.platformFee / 100).toFixed(2) }}</span>
        <span>¥{{ (item.playerAmount / 100).toFixed(2) }}</span>
        <span>{{ new Date(item.createdAt).toLocaleString() }}</span>
      </div>
      <div v-if="!records.length" class="empty-row">暂无消费记录</div>
    </div>
  </section>
</template>

<style scoped>
.users-table .tr{grid-template-columns:1.8fr 1fr .7fr 1fr .8fr 1.6fr}.records-table .tr{grid-template-columns:1.5fr .8fr .9fr .9fr .9fr 1.2fr}.badge.danger{background:rgba(239,68,68,.12);color:#ef4444}.detail-panel{margin-top:18px}.empty-row{padding:34px;color:#6b7280;text-align:center;border-top:1px solid rgba(0,0,0,.06);font-size:12px}
</style>
