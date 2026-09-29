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
      <view class="title">{{ gameName }}</view>
      <view class="subtitle">选择服务套餐，确认后创建订单</view>
    </view>

    <view class="sku-list">
      <view
        v-for="sku in skus"
        :key="sku.id"
        class="sku-card"
        :class="{ selected: selectedId === sku.id }"
        @click="selectedId = sku.id"
      >
        <view class="check">{{ selectedId === sku.id ? "✓" : "" }}</view>
        <view class="sku-main">
          <view class="sku-name">{{ sku.name }}</view>
          <view class="meta">{{ sku.duration_minutes }} 分钟 · {{ sku.service_type }}</view>
        </view>
        <view class="price">¥{{ (sku.price / 100).toFixed(2) }}</view>
      </view>
    </view>

    <view class="remark-card">
      <view class="label">给陪玩留言 <text>选填</text></view>
      <textarea
        v-model="remark"
        maxlength="500"
        placeholder="例如：娱乐局、开麦、想练辅助位…"
      />
    </view>

    <view class="footer">
      <view>
        <text class="pay-label">合计</text>
        <text v-if="selected" class="total">¥{{ (selected.price / 100).toFixed(2) }}</text>
      </view>
      <button
        class="buy"
        :disabled="!selected"
        :loading="creating"
        @click="createOrder"
      >
        确认下单
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx 28rpx 180rpx; }
.heading { margin: 12rpx 0 26rpx; }
.title { font-size: 40rpx; font-weight: 800; }
.subtitle { margin-top: 10rpx; color: #92929d; font-size: 23rpx; }
.sku-list { display: flex; flex-direction: column; gap: 18rpx; }
.sku-card { padding: 28rpx; border: 2rpx solid transparent; border-radius: 30rpx; background: #fff; display: flex; align-items: center; gap: 20rpx; }
.sku-card.selected { border-color: #6c5ce7; box-shadow: 0 10rpx 32rpx rgba(108,92,231,.08); }
.check { width: 38rpx; height: 38rpx; border-radius: 50%; border: 2rpx solid #d7d6df; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 20rpx; }
.selected .check { border-color: #6c5ce7; background: #6c5ce7; }
.sku-main { flex: 1; min-width: 0; }
.sku-name { font-size: 28rpx; font-weight: 700; }
.meta { margin-top: 10rpx; color: #92929d; font-size: 21rpx; }
.price { color: #6c5ce7; font-size: 31rpx; font-weight: 800; }
.remark-card { margin-top: 22rpx; padding: 28rpx; border-radius: 30rpx; background: #fff; }
.label { font-size: 25rpx; font-weight: 700; }
.label text { margin-left: 8rpx; color: #aaaab4; font-size: 20rpx; font-weight: 400; }
textarea { width: 100%; height: 150rpx; margin-top: 20rpx; font-size: 24rpx; }
.footer { position: fixed; left: 0; right: 0; bottom: 0; z-index: 10; padding: 20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom)); background: rgba(255,255,255,.97); border-top: 1rpx solid #ececf2; display: flex; align-items: center; justify-content: space-between; }
.pay-label { display: block; color: #92929d; font-size: 20rpx; }
.total { display: block; margin-top: 4rpx; font-size: 36rpx; font-weight: 800; }
.buy { margin: 0; width: 300rpx; height: 84rpx; line-height: 84rpx; border-radius: 25rpx; background: #6c5ce7; color: #fff; font-size: 26rpx; font-weight: 700; }
.buy[disabled] { opacity: .45; }
</style>
