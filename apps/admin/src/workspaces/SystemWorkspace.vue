<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import type { AdminUser, OperationLog } from "../types/admin"

type SystemView = "roles" | "logs"

const view = ref<SystemView>("roles")
const users = ref<AdminUser[]>([])
const logs = ref<OperationLog[]>([])
const loadingUsers = ref(false)
const loadingLogs = ref(false)
const error = ref("")
const query = ref("")
const roleFilter = ref<"ALL" | "PLATFORM" | "USER">("ALL")
const updatingUserId = ref("")

const platformUsers = computed(() =>
  users.value.filter(user => user.effectiveRoles.includes("PLATFORM"))
)

const filteredUsers = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return users.value.filter(user => {
    const matchesRole =
      roleFilter.value === "ALL" ||
      (roleFilter.value === "PLATFORM"
        ? user.effectiveRoles.includes("PLATFORM")
        : !user.effectiveRoles.includes("PLATFORM"))
    const matchesKeyword = !keyword || [
      user.nickname,
      user.phone ?? "",
      user.openid ?? "",
      user.id
    ].some(value => value.toLowerCase().includes(keyword))
    return matchesRole && matchesKeyword
  })
})

function roleLabel(role: string) {
  return ({
    USER: "普通用户",
    PLAYER: "陪玩",
    PLATFORM: "平台管理员",
    ADMIN: "平台管理员"
  } as Record<string, string>)[role] ?? role
}

function logDetail(item: OperationLog) {
  if (item.fromRole || item.toRole) return `${item.fromRole || "-"} -> ${item.toRole || "-"}`
  if (item.fromStatus || item.toStatus) return `${item.fromStatus || "-"} -> ${item.toStatus || "-"}`
  return item.reason || "-"
}

async function loadUsers() {
  loadingUsers.value = true
  error.value = ""
  try {
    users.value = await adminRequest<AdminUser[]>("/admin/users?limit=300")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "用户权限加载失败"
  } finally {
    loadingUsers.value = false
  }
}

async function loadLogs() {
  loadingLogs.value = true
  error.value = ""
  try {
    logs.value = await adminRequest<OperationLog[]>("/admin/operation-logs")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "操作日志加载失败"
  } finally {
    loadingLogs.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadUsers(), loadLogs()])
}

async function updateRole(user: AdminUser, role: "USER" | "PLATFORM") {
  const reason = window.prompt(
    role === "PLATFORM" ? "请输入授予平台管理员权限的原因" : "请输入撤销平台管理员权限的原因",
    role === "PLATFORM" ? "授予平台管理员权限" : "撤销平台管理员权限"
  )
  if (!reason?.trim()) return
  updatingUserId.value = user.id
  error.value = ""
  try {
    await adminRequest<AdminUser>(`/admin/users/${user.id}/role`, {
      method: "PATCH",
      body: { role, reason: reason.trim() }
    })
    await refreshAll()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "权限更新失败"
  } finally {
    updatingUserId.value = ""
  }
}

onMounted(refreshAll)
</script>

<template>
  <div class="subnav">
    <button :class="{ active: view === 'roles' }" @click="view = 'roles'">权限管理</button>
    <button :class="{ active: view === 'logs' }" @click="view = 'logs'">操作日志</button>
  </div>

  <section v-if="view === 'roles'" class="panel">
    <div class="panel-head">
      <div>
        <h2>权限管理</h2>
        <p>平台管理员可以授予或撤销用户的 PLATFORM 权限；PLAYER 权限由陪玩认证通过后自动派生。</p>
      </div>
      <div class="head-actions">
        <span class="count">{{ platformUsers.length }} 个平台管理员</span>
        <button class="refresh" @click="loadUsers">刷新</button>
      </div>
    </div>

    <div class="permission-note">
      <strong>小程序联动</strong>
      <span>用户刷新资料或重新登录后，/api/user/me 会返回最新 role；平台管理员会开放后台/陪玩入口，陪玩接单仍要求陪玩与技能认证通过。</span>
    </div>

    <div class="permission-toolbar">
      <input v-model="query" placeholder="搜索昵称、手机号、OpenID、用户 ID" />
      <select v-model="roleFilter">
        <option value="ALL">全部用户</option>
        <option value="PLATFORM">平台管理员</option>
        <option value="USER">非平台管理员</option>
      </select>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loadingUsers" class="loading">正在读取用户权限...</div>
    <div v-else class="table permissions-table">
      <div class="tr th">
        <span>用户</span>
        <span>基础角色</span>
        <span>有效权限</span>
        <span>状态</span>
        <span>消费</span>
        <span>操作</span>
      </div>
      <div v-for="user in filteredUsers" :key="user.id" class="tr">
        <span class="identity">
          <b>{{ user.nickname || "未命名用户" }}</b>
          <small>{{ user.id.slice(0, 8) }} · {{ user.phone || user.openid || "未绑定" }}</small>
        </span>
        <span><em class="badge">{{ user.roleText || roleLabel(user.role) }}</em></span>
        <span class="role-badges">
          <em v-for="role in user.effectiveRoles" :key="role" class="badge" :class="{ green: role === 'PLATFORM' }">
            {{ roleLabel(role) }}
          </em>
          <small v-if="!user.effectiveRoles.length">无有效权限</small>
        </span>
        <span><em class="badge" :class="{ danger: user.statusCode !== 'ACTIVE' }">{{ user.status }}</em></span>
        <span class="identity">
          <b>¥{{ (user.totalSpent / 100).toFixed(2) }}</b>
          <small>{{ user.orderCount }} 单</small>
        </span>
        <span class="actions">
          <button
            v-if="!user.effectiveRoles.includes('PLATFORM')"
            class="approve"
            :disabled="updatingUserId === user.id"
            @click="updateRole(user, 'PLATFORM')"
          >授予 PLATFORM</button>
          <button
            v-else
            class="reject"
            :disabled="updatingUserId === user.id"
            @click="updateRole(user, 'USER')"
          >撤销 PLATFORM</button>
        </span>
      </div>
      <div v-if="!filteredUsers.length" class="empty-row">暂无匹配用户</div>
    </div>
  </section>

  <section v-else class="panel">
    <div class="panel-head">
      <div>
        <h2>操作日志</h2>
        <p>展示谁在什么时候对哪个资源执行了什么操作；日志只读，不允许删除。</p>
      </div>
      <button class="refresh" @click="loadLogs">刷新</button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loadingLogs" class="loading">正在读取操作日志...</div>
    <div v-else class="table logs-table">
      <div class="tr th">
        <span>时间</span>
        <span>操作者</span>
        <span>动作</span>
        <span>资源</span>
        <span>结果</span>
        <span>详情</span>
      </div>
      <div v-for="item in logs" :key="item.source + item.id" class="tr">
        <span>{{ new Date(item.createdAt).toLocaleString() }}</span>
        <span class="identity"><b>{{ item.actorUserId.slice(0, 8) || "系统" }}</b><small>{{ item.source }}</small></span>
        <span>{{ item.action }}</span>
        <span class="identity"><b>{{ item.resourceType }}</b><small>{{ item.resourceId }}</small></span>
        <span><em class="badge green">{{ item.decision }}</em></span>
        <span>{{ logDetail(item) }}</span>
      </div>
      <div v-if="!logs.length" class="empty-row">暂无操作日志</div>
    </div>
  </section>
</template>

<style scoped>
.head-actions{display:flex;align-items:center;gap:10px}.permission-note{display:flex;gap:14px;align-items:flex-start;margin-bottom:18px;padding:14px 16px;border:1px solid rgba(0,0,0,.08);border-radius:14px;background:#f8fafc}.permission-note strong{white-space:nowrap;color:#111827}.permission-note span{color:#6b7280;font-size:12px;line-height:1.7}.permission-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) 180px;gap:12px;margin-bottom:18px}.permission-toolbar input,.permission-toolbar select{height:42px;padding:0 13px;border-radius:12px}.permissions-table .tr{grid-template-columns:1.6fr .9fr 1.4fr .7fr .8fr 1.2fr}.logs-table .tr{grid-template-columns:1.1fr .9fr 1fr 1.4fr .7fr 1fr}.role-badges{display:flex;flex-wrap:wrap;gap:6px}.badge.danger{background:rgba(239,68,68,.12);color:#ef4444}.actions button:disabled{opacity:.5;cursor:not-allowed}.empty-row{padding:34px;color:#6b7280;text-align:center;border-top:1px solid rgba(0,0,0,.06);font-size:12px}@media(max-width:1200px){.permission-toolbar{grid-template-columns:1fr}.permissions-table .tr{grid-template-columns:1.4fr .8fr 1fr .7fr .8fr 1.1fr}}
</style>
