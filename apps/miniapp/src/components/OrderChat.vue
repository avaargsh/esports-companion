<script setup lang="ts">
import { ref, watch } from "vue"

import { request } from "../api/client"
import type { OrderMessage } from "../types/domain"

const props = withDefaults(
  defineProps<{
    orderId: string
    userId: string
    refreshKey?: number
    dark?: boolean
    writable?: boolean
  }>(),
  {
    refreshKey: 0,
    dark: false,
    writable: true
  }
)

const messages = ref<OrderMessage[]>([])
const content = ref("")
const loading = ref(false)
const sending = ref(false)
const error = ref("")

async function load() {
  if (!props.orderId || !props.userId) return
  loading.value = true
  error.value = ""
  try {
    messages.value = await request<OrderMessage[]>(
      `/orders/${props.orderId}/messages?limit=100`,
      { userId: props.userId }
    )
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "MESSAGE_LOAD_FAILED"
  } finally {
    loading.value = false
  }
}

async function send() {
  const text = content.value.trim()
  if (!text || sending.value || !props.orderId || !props.userId || !props.writable) return

  sending.value = true
  error.value = ""
  const clientMessageId =
    `miniapp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
  try {
    await request<OrderMessage>(`/orders/${props.orderId}/messages`, {
      method: "POST",
      userId: props.userId,
      data: {
        client_message_id: clientMessageId,
        content: text
      }
    })
    content.value = ""
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "MESSAGE_SEND_FAILED"
  } finally {
    sending.value = false
  }
}

watch(
  () => [props.orderId, props.userId],
  () => { void load() },
  { immediate: true }
)
watch(
  () => props.refreshKey,
  () => { void load() }
)
</script>

<template>
  <view class="chat" :class="{ dark }">
    <view class="chat-head">
      <view>
        <view class="chat-title">订单沟通</view>
        <view class="chat-hint">只用于本单服务沟通，订单结束后保留为记录。</view>
      </view>
      <text class="chat-count">{{ messages.length }}</text>
    </view>

    <view v-if="error" class="chat-error">{{ error }}</view>
    <view v-if="loading && messages.length === 0" class="chat-empty">加载消息中…</view>
    <view v-else-if="messages.length === 0" class="chat-empty">还没有消息</view>

    <scroll-view
      v-else
      class="message-list"
      scroll-y
      :scroll-into-view="`msg-${messages[messages.length - 1]?.id}`"
    >
      <view
        v-for="message in messages"
        :id="`msg-${message.id}`"
        :key="message.id"
        class="message-row"
        :class="{ mine: message.sender_user_id === userId }"
      >
        <view class="message-meta">
          {{ message.sender_user_id === userId
            ? "我"
            : message.sender_role === "PLAYER" ? "大神" : "老板" }}
        </view>
        <view class="bubble">{{ message.content }}</view>
      </view>
    </scroll-view>

    <view v-if="writable" class="composer">
      <textarea
        v-model="content"
        maxlength="1000"
        auto-height
        placeholder="围绕本单服务沟通…"
      />
      <button
        class="send"
        :disabled="!content.trim()"
        :loading="sending"
        @click="send"
      >
        发送
      </button>
    </view>
    <view v-else class="read-only">订单已结束，会话保留为只读售后记录。</view>
  </view>
</template>

<style scoped>
.chat{margin-top:16rpx;padding:25rpx;border:1rpx solid rgba(20,20,30,.035);border-radius:29rpx;background:#fff;color:var(--ink);box-shadow:var(--shadow-card)}.chat.dark{border-color:rgba(255,255,255,.05);background:#191920;color:#fff;box-shadow:none}.chat-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18rpx}.chat-title{font-size:24rpx;font-weight:780}.chat-hint{margin-top:6rpx;color:var(--muted);font-size:17rpx;line-height:1.5}.chat-count{min-width:38rpx;height:38rpx;padding:0 8rpx;line-height:38rpx;border-radius:999rpx;background:var(--brand-soft);color:var(--brand);text-align:center;font-size:15rpx;font-weight:700}.dark .chat-count{background:rgba(103,87,230,.14);color:#aa9df8}
.message-list{height:350rpx;margin-top:18rpx;padding:5rpx 0}.message-row{display:flex;flex-direction:column;align-items:flex-start;margin:13rpx 0}.message-row.mine{align-items:flex-end}.message-meta{margin-bottom:5rpx;color:#9998a2;font-size:15rpx}.bubble{max-width:82%;padding:14rpx 18rpx;border-radius:19rpx 19rpx 19rpx 6rpx;background:#f2f2f6;font-size:20rpx;line-height:1.55;word-break:break-word}.mine .bubble{border-radius:19rpx 19rpx 6rpx 19rpx;background:#6757e6;color:#fff}.dark .bubble{background:#24242d;color:#e3e1e8}.dark .mine .bubble{background:#6757e6;color:#fff}
.chat-empty,.chat-error,.read-only{margin-top:18rpx;padding:20rpx;border-radius:18rpx;text-align:center;font-size:18rpx}.chat-empty,.read-only{background:#f7f7fa;color:var(--muted)}.dark .chat-empty,.dark .read-only{background:#23232b;color:#777582}.chat-error{background:var(--danger-soft);color:var(--danger)}
.composer{display:flex;align-items:flex-end;gap:10rpx;margin-top:17rpx}.composer textarea{flex:1;min-height:66rpx;max-height:170rpx;padding:15rpx 18rpx;border-radius:19rpx;background:#f7f7fa;font-size:20rpx}.dark .composer textarea{background:#23232c;color:#fff}.send{width:116rpx;height:66rpx;margin:0;line-height:66rpx;border-radius:19rpx;background:#6757e6;color:#fff;font-size:19rpx;font-weight:740}.send[disabled]{opacity:.4}
</style>