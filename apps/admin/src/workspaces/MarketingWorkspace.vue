<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"

import { adminRequest } from "../api"
import type { Announcement } from "../types/admin"

const rows = ref<Announcement[]>([])
const loading = ref(false)
const error = ref("")
const form = reactive({ title: "", content: "", noticeType: "NORMAL" as "NORMAL" | "SYSTEM" })

async function load() {
  loading.value = true
  error.value = ""
  try {
    rows.value = await adminRequest<Announcement[]>("/admin/announcements")
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "公告加载失败"
  } finally {
    loading.value = false
  }
}

async function createAnnouncement() {
  if (!form.title.trim()) {
    error.value = "请填写公告标题"
    return
  }
  try {
    await adminRequest("/admin/announcements", {
      method: "POST",
      body: {
        title: form.title.trim(),
        content: form.content.trim(),
        audience: "ALL",
        notice_type: form.noticeType
      }
    })
    form.title = ""
    form.content = ""
    form.noticeType = "NORMAL"
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "公告创建失败"
  }
}

async function changeStatus(item: Announcement, action: "publish" | "offline") {
  try {
    await adminRequest(`/admin/announcements/${item.id}/${action}`, { method: "POST" })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "公告状态更新失败"
  }
}

onMounted(load)
</script>

<template>
  <section class="panel notice-editor">
    <div class="panel-head">
      <div>
        <h2>系统通知推送</h2>
        <p>普通通知显示在小程序首页通知栏；系统通知会在用户打开小程序后弹窗展示。</p>
      </div>
      <button class="refresh" @click="load">刷新</button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div class="notice-form">
      <input v-model="form.title" placeholder="公告标题" />
      <select v-model="form.noticeType">
        <option value="NORMAL">普通通知：首页流动展示</option>
        <option value="SYSTEM">系统通知：打开小程序弹窗</option>
      </select>
      <textarea v-model="form.content" placeholder="公告内容"></textarea>
      <button class="approve" @click="createAnnouncement">新增公告</button>
    </div>
  </section>

  <section class="panel">
    <div class="panel-head">
      <div>
        <h2>公告列表</h2>
        <p>运营公告保留创建、发布、下线记录。</p>
      </div>
      <span class="count">{{ rows.length }} 条</span>
    </div>
    <div v-if="loading" class="loading">正在读取公告...</div>
    <div v-else class="table announcements-table">
      <div class="tr th">
        <span>公告</span>
        <span>类型</span>
        <span>状态</span>
        <span>发布时间</span>
        <span>操作</span>
      </div>
      <div v-for="item in rows" :key="item.id" class="tr">
        <span class="identity"><b>{{ item.title }}</b><small>{{ item.content || "无内容" }}</small></span>
        <span>{{ item.noticeTypeText }}</span>
        <span><em class="badge green">{{ item.status }}</em></span>
        <span>{{ item.publishedAt ? new Date(item.publishedAt).toLocaleString() : "未发布" }}</span>
        <span class="actions">
          <button v-if="item.statusCode !== 'PUBLISHED'" class="approve" @click="changeStatus(item, 'publish')">发布</button>
          <button v-if="item.statusCode === 'PUBLISHED'" class="reject" @click="changeStatus(item, 'offline')">下线</button>
          <small v-if="item.statusCode === 'OFFLINE'">已下线</small>
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.notice-form{display:grid;grid-template-columns:1.2fr .7fr auto;gap:12px}.notice-form textarea{grid-column:1 / -1;min-height:110px;resize:vertical}.notice-form input,.notice-form textarea,.notice-form select{padding:12px 14px;border-radius:12px}.announcements-table .tr{grid-template-columns:1.8fr .7fr .7fr 1.1fr 1fr}
</style>
