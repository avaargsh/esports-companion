<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order, ServiceSku } from "../../types/domain"

const gameId = ref("")
const gameName = ref("选择服务")
const skus = ref<ServiceSku[]>([])
const selectedId = ref("")
const remark = ref("")
const creating = ref(false)

const selected = computed(() =>
  skus.value.find(item => item.id === selectedId.value) ?? null
)
const serviceSummary = computed(() =>
  selected.value ? `${selected.value.duration_minutes} 分钟 · ${selected.value.service_type}` : "请选择服务"
)

onLoad(async query => {
  gameId.value = String(query?.id ?? "")
  gameName.value = decodeURIComponent(String(query?.name ?? "选择服务"))
  if (!gameId.value) return

  skus.value = await request<ServiceSku[]>(`/games/${gameId.value}/skus`)
  selectedId.value = skus.value[0]?.id ?? ""
})

async function createOrder() {
  if (!selected.value || creating.value) return
  creating.value = true
  try {
    const identities = await getDemoIdentities()
    const order = await request<Order>("/orders", {
      method: "POST",
      userId: identities.customer.userId,
      data: {
        sku_id: selected.value.id,
        quantity: 1,
        remark: remark.value.trim()
      }
    })
    uni.redirectTo({ url: `/pages/order-detail/index?id=${order.id}` })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "下单失败",
      icon: "none"
    })
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <view class="page">
    <view class="heading">
      <text class="step">STEP 1 / 2</text>
      <view class="title">{{ gameName }}</view>
      <view class="subtitle">选择适合你的陪玩服务</view>
    </view>

    <view class="section-title">服务规格</view>
    <view class="sku-list">
      <view
        v-for="sku in skus"
        :key="sku.id"
        class="sku-card"
        :class="{ selected: selectedId === sku.id }"
        @click="selectedId = sku.id"
      >
        <view class="check"><view v-if="selectedId === sku.id"></view></view>
        <view class="sku-main">
          <view class="sku-name">{{ sku.name }}</view>
          <view class="meta">{{ sku.duration_minutes }} 分钟 · {{ sku.service_type }}</view>
        </view>
        <view class="price"><text>¥</text>{{ (sku.price / 100).toFixed(0) }}</view>
      </view>
    </view>

    <view class="remark-card">
      <view class="remark-head">
        <view class="label">服务偏好</view>
        <text class="optional">选填</text>
      </view>
      <textarea
        v-model="remark"
        maxlength="500"
        placeholder="例如：钻石段位、辅助位、希望开麦沟通…"
      />
      <view class="counter">{{ remark.length }}/500</view>
    </view>

    <view class="assurance">
      <view><text>✓</text> 服务开始前可取消</view>
      <view><text>✓</text> 完成确认后再结算给陪玩师</view>
    </view>

    <view class="footer">
      <view>
        <text class="pay-label">{{ serviceSummary }}</text>
        <text v-if="selected" class="total">¥{{ (selected.price / 100).toFixed(2) }}</text>
      </view>
      <button
        class="buy"
        :disabled="!selected || creating"
        :loading="creating"
        @click="createOrder"
      >
        {{ creating ? "创建中…" : "确认下单" }}
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { padding:28rpx 28rpx 190rpx; }
.heading { padding:10rpx 2rpx 34rpx; }
.step { color:#6c5ce7; font-size:18rpx; font-weight:750; letter-spacing:2rpx; }
.title { margin-top:10rpx; font-size:40rpx; font-weight:850; }
.subtitle { margin-top:8rpx; color:#9999a3; font-size:22rpx; }
.section-title { margin-bottom:16rpx; font-size:25rpx; font-weight:750; }
.sku-list { display:flex; flex-direction:column; gap:14rpx; }
.sku-card { display:flex; align-items:center; gap:18rpx; padding:28rpx; border:2rpx solid transparent; border-radius:30rpx; background:#fff; transition:.16s; }
.sku-card.selected { border-color:#6c5ce7; box-shadow:0 12rpx 36rpx rgba(108,92,231,.09); }
.check { width:36rpx; height:36rpx; flex:none; padding:7rpx; border:2rpx solid #d5d5dd; border-radius:50%; }
.selected .check { border-color:#6c5ce7; }
.check view { width:100%; height:100%; border-radius:50%; background:#6c5ce7; }
.sku-main { flex:1; min-width:0; }
.sku-name { font-size:27rpx; font-weight:760; }
.meta { margin-top:8rpx; color:#9999a3; font-size:20rpx; }
.price { color:#17171e; font-size:35rpx; font-weight:850; }
.price text { margin-right:2rpx; font-size:21rpx; }
.remark-card { position:relative; margin-top:22rpx; padding:28rpx; border-radius:30rpx; background:#fff; }
.remark-head { display:flex; gap:10rpx; align-items:center; }
.label { font-size:25rpx; font-weight:750; }
.optional { color:#aaaab3; font-size:19rpx; }
textarea { width:100%; height:150rpx; margin-top:18rpx; color:#34343d; font-size:23rpx; line-height:1.6; }
.counter { position:absolute; right:26rpx; bottom:22rpx; color:#b0b0b8; font-size:18rpx; }
.assurance { margin-top:22rpx; padding:4rpx 8rpx; color:#777782; font-size:20rpx; line-height:1.9; }
.assurance text { color:#1ca05b; font-weight:800; }
.footer { position:fixed; z-index:10; left:0; right:0; bottom:0; padding:20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom)); background:rgba(255,255,255,.96); border-top:1rpx solid #ececf2; display:flex; align-items:center; justify-content:space-between; backdrop-filter:blur(18rpx); }
.pay-label { display:block; max-width:320rpx; overflow:hidden; color:#9999a3; font-size:18rpx; white-space:nowrap; text-overflow:ellipsis; }
.total { display:block; margin-top:3rpx; font-size:37rpx; font-weight:850; }
.buy { margin:0; width:306rpx; height:84rpx; line-height:84rpx; border-radius:25rpx; background:#6c5ce7; color:#fff; font-size:25rpx; font-weight:750; }
.buy[disabled] { opacity:.45; }
</style>
