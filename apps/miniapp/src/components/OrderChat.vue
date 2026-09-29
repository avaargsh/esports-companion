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
        <view class="chat-hint">仅当前订单参与方可见，不支持好友或私聊关系。</view>
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
.chat { margin-top: 22rpx; padding: 28rpx; border-radius: 30rpx; background: #fff; color: #17171f; }
.chat.dark { background: #181820; color: #fff; }
.chat-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20rpx; }
.chat-title { font-size: 28rpx; font-weight: 750; }
.chat-hint { margin-top: 7rpx; color: #92929d; font-size: 19rpx; line-height: 1.5; }
.chat-count { min-width: 44rpx; height: 44rpx; line-height: 44rpx; padding: 0 10rpx; border-radius: 999rpx; background: #f1efff; color: #6c5ce7; text-align: center; font-size: 18rpx; }
.dark .chat-count { background: rgba(108,92,231,.18); color: #9e92ff; }
.message-list { height: 380rpx; margin-top: 22rpx; padding: 8rpx 0; }
.message-row { display: flex; flex-direction: column; align-items: flex-start; margin: 16rpx 0; }
.message-row.mine { align-items: flex-end; }
.message-meta { margin-bottom: 6rpx; color: #a0a0aa; font-size: 17rpx; }
.bubble { max-width: 82%; padding: 16rpx 20rpx; border-radius: 20rpx 20rpx 20rpx 6rpx; background: #f4f4f8; font-size: 22rpx; line-height: 1.55; word-break: break-word; }
.mine .bubble { border-radius: 20rpx 20rpx 6rpx 20rpx; background: #6c5ce7; color: #fff; }
.dark .bubble { background: #25252e; color: #e8e8ed; }
.dark .mine .bubble { background: #6c5ce7; color: #fff; }
.chat-empty, .chat-error, .read-only { margin-top: 22rpx; padding: 24rpx; border-radius: 20rpx; text-align: center; font-size: 20rpx; }
.chat-empty { color: #92929d; background: #f8f8fb; }
.read-only { padding: 18rpx; border-radius: 18rpx; color: #92929d; background: #f8f8fb; text-align: center; font-size: 19rpx; }
.dark .chat-empty { background: #212129; color: #777784; }
.dark .read-only { background: #212129; color: #777784; }
.chat-error { background: #fff0f0; color: #c63d3d; }
.composer { display: flex; align-items: flex-end; gap: 14rpx; margin-top: 20rpx; }
.composer textarea { flex: 1; min-height: 70rpx; max-height: 180rpx; padding: 17rpx 20rpx; border-radius: 20rpx; background: #f7f7fb; box-sizing: border-box; font-size: 22rpx; }
.dark .composer textarea { background: #25252e; color: #fff; }
.send { width: 132rpx; height: 70rpx; line-height: 70rpx; margin: 0; border-radius: 20rpx; background: #6c5ce7; color: #fff; font-size: 22rpx; }
.send[disabled] { opacity: .45; }
</style>
