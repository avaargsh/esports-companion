<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"
import type { OperationLog } from "../types/admin"

type SystemView = "roles" | "logs"

const view = ref<SystemView>("logs")
const logs = ref<OperationLog[]>([])
const loading = ref(false)
const error = ref("")

const platformActors = computed(() =>
  Array.from(new Set(logs.value.map(item => item.actorUserId).filter(Boolean)))
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    logs.value = await adminRequest<OperationLog[]>("/admin/operation-logs")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "操作日志加载失败"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="subnav">
    <button :class="{ active: view === 'logs' }" @click="view = 'logs'">操作日志</button>
    <button :class="{ active: view === 'roles' }" @click="view = 'roles'">权限管理</button>
  </div>

  <section v-if="view === 'roles'" class="panel">
    <div class="panel-head">
      <div>
        <h2>权限管理</h2>
        <p>当前后台只允许 PLATFORM 管理员进入，真实登录由微信扫码后的角色判断控制。</p>
      </div>
      <span class="count">{{ platformActors.length }} 个操作者</span>
    </div>
    <div class="role-grid">
      <article>
        <b>PLATFORM</b>
        <span>可访问后台全部管理接口</span>
      </article>
      <article>
        <b>审计只读</b>
        <span>操作日志不提供删除入口，保留完整追踪链路</span>
      </article>
      <article>
        <b>真实账号</b>
        <span>Header 状态仅展示当前登录模式，不作为权限开关</span>
      </article>
    </div>
  </section>

  <section v-else class="panel">
    <div class="panel-head">
      <div>
        <h2>操作日志</h2>
        <p>展示谁在什么时候对哪个资源执行了什么操作；日志只读，不允许删除。</p>
      </div>
      <button class="refresh" @click="load">刷新</button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="loading" class="loading">正在读取操作日志...</div>
    <div v-else class="table logs-table">
      <div class="tr th">
        <span>时间</span>
        <span>操作者</span>
        <span>动作</span>
        <span>资源</span>
        <span>结果</span>
        <span>原因</span>
      </div>
      <div v-for="item in logs" :key="item.source + item.id" class="tr">
        <span>{{ new Date(item.createdAt).toLocaleString() }}</span>
        <span class="identity"><b>{{ item.actorUserId.slice(0, 8) || "系统" }}</b><small>{{ item.source }}</small></span>
        <span>{{ item.action }}</span>
        <span class="identity"><b>{{ item.resourceType }}</b><small>{{ item.resourceId }}</small></span>
        <span><em class="badge green">{{ item.decision }}</em></span>
        <span>{{ item.reason || "-" }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.logs-table .tr{grid-template-columns:1.1fr .9fr 1fr 1.4fr .7fr 1fr}.role-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.role-grid article{padding:22px;border:1px solid rgba(0,0,0,.08);border-radius:14px;background:#f8fafc}.role-grid b,.role-grid span{display:block}.role-grid b{font-size:18px}.role-grid span{margin-top:10px;color:#6b7280;font-size:12px;line-height:1.6}
</style>
