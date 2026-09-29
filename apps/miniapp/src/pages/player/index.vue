<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"

import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order, PublicOffering, PublicPlayer } from "../../types/domain"

const playerId = ref("")
const player = ref<PublicPlayer | null>(null)
const selectedOfferingId = ref("")
const remark = ref("")
const quantity = ref(1)
const loading = ref(true)
const creating = ref(false)

const selectedOffering = computed<PublicOffering | null>(() =>
  player.value?.offerings.find(item => item.id === selectedOfferingId.value) ?? null
)
const totalAmount = computed(() => (selectedOffering.value?.price || 0) * quantity.value)

function changeQuantity(delta: number) {
  quantity.value = Math.min(10, Math.max(1, quantity.value + delta))
}

onLoad(async query => {
  playerId.value = String(query?.id ?? "")
  if (!playerId.value) return
  try {
    player.value = await request<PublicPlayer>(`/players/${playerId.value}`)
    selectedOfferingId.value = player.value.offerings[0]?.id ?? ""
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "大神资料加载失败",
      icon: "none"
    })
  } finally {
    loading.value = false
  }
})

async function createDesignatedOrder() {
  if (!selectedOffering.value || creating.value) return
  creating.value = true
  try {
    const identities = await getDemoIdentities()
    const order = await request<Order>("/orders", {
      method: "POST",
      userId: identities.customer.userId,
      data: {
        offering_id: selectedOffering.value.id,
        quantity: quantity.value,
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
  <view v-if="loading" class="page">
    <view class="empty">正在加载大神资料…</view>
  </view>

  <view v-else-if="player" class="page">
    <view class="profile-card">
      <image v-if="player.avatar_url" class="avatar-image" :src="player.avatar_url" mode="aspectFill" />
      <view v-else class="avatar">{{ player.display_name.slice(0, 1) }}</view>
      <view class="profile-main">
        <view class="name-row">
          <text class="name">{{ player.display_name }}</text>
          <text class="online">{{ player.service_status === "AVAILABLE" ? "可接单" : "暂离" }}</text>
        </view>
        <view class="rating">
          {{ player.rating > 0 ? player.rating.toFixed(1) + " ★" : "暂无评分" }}
          · {{ player.review_count }} 条评价
        </view>
        <view class="bio">{{ player.bio || "这个大神还没有填写自我介绍。" }}</view>
      </view>
    </view>

    <view v-if="player.skills.length" class="section">
      <view class="section-title">已认证技能</view>
      <view class="skill-list">
        <view v-for="skill in player.skills" :key="skill.id" class="skill-badge">
          <text class="skill-game">{{ skill.game_name }}</text>
          <text class="skill-rank">{{ skill.rank }}</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-title">选择服务</view>
      <view
        v-for="offering in player.offerings"
        :key="offering.id"
        class="offering"
        :class="{ selected: selectedOfferingId === offering.id }"
        @click="selectedOfferingId = offering.id"
      >
        <view class="check">{{ selectedOfferingId === offering.id ? "✓" : "" }}</view>
        <view class="offering-main">
          <view class="offering-name">{{ offering.game_name }} · {{ offering.sku_name }}</view>
          <view class="offering-desc">{{ offering.description || offering.service_type }}</view>
          <view class="offering-meta">{{ offering.duration_minutes }} 分钟</view>
        </view>
        <view class="price">¥{{ (offering.price / 100).toFixed(2) }}</view>
      </view>
    </view>

    <view class="section-card quantity-card">
      <view>
        <view class="section-title compact">服务数量</view>
        <view class="quantity-hint">指定大神，同一 Offering 可购买 1–10 份</view>
      </view>
      <view class="stepper">
        <button :disabled="quantity <= 1" @click="changeQuantity(-1)">−</button>
        <text>{{ quantity }}</text>
        <button :disabled="quantity >= 10" @click="changeQuantity(1)">＋</button>
      </view>
    </view>

    <view class="section-card">
      <view class="section-title">给大神留言 <text class="optional">选填</text></view>
      <textarea
        v-model="remark"
        maxlength="500"
        placeholder="例如：娱乐局、开麦、想练辅助位…"
      />
    </view>

    <view class="section">
      <view class="section-title">最近评价</view>
      <view v-if="player.reviews.length === 0" class="empty">暂无评价</view>
      <view v-for="review in player.reviews" :key="review.id" class="review">
        <view class="review-rating">{{ "★".repeat(review.rating) }}</view>
        <view class="review-content">{{ review.content || "用户未填写文字评价" }}</view>
      </view>
    </view>

    <view class="footer">
      <view>
        <text class="footer-label">指定大神</text>
        <text v-if="selectedOffering" class="footer-price">
          ¥{{ (totalAmount / 100).toFixed(2) }}
        </text>
      </view>
      <button
        class="buy"
        :disabled="!selectedOffering || player.service_status !== 'AVAILABLE'"
        :loading="creating"
        @click="createDesignatedOrder"
      >
        指定下单
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx 28rpx 190rpx; }
.profile-card { display: flex; gap: 24rpx; padding: 32rpx; border-radius: 34rpx; background: linear-gradient(145deg,#17171f,#29263a); color: #fff; }
.avatar, .avatar-image { width: 112rpx; height: 112rpx; border-radius: 34rpx; flex-shrink: 0; }
.avatar { display: flex; align-items: center; justify-content: center; background: #6c5ce7; font-size: 40rpx; font-weight: 800; }
.profile-main { flex: 1; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 12rpx; }
.name { font-size: 34rpx; font-weight: 800; }
.online { padding: 6rpx 12rpx; border-radius: 999rpx; background: rgba(71,209,130,.15); color: #65e39b; font-size: 18rpx; }
.rating { margin-top: 10rpx; color: #c5c4cf; font-size: 21rpx; }
.bio { margin-top: 16rpx; color: #aaaab4; font-size: 22rpx; line-height: 1.6; }
.section { margin-top: 34rpx; }
.section-title { margin-bottom: 18rpx; font-size: 29rpx; font-weight: 800; }
.skill-list { display: flex; flex-wrap: wrap; gap: 12rpx; }
.skill-badge { display: flex; gap: 8rpx; align-items: center; padding: 12rpx 16rpx; border-radius: 18rpx; background: #eefbf4; }
.skill-game { color: #16824d; font-size: 20rpx; font-weight: 700; }
.skill-rank { color: #4f8068; font-size: 20rpx; }
.offering { display: flex; gap: 18rpx; align-items: center; margin-bottom: 16rpx; padding: 26rpx; border: 2rpx solid transparent; border-radius: 28rpx; background: #fff; }
.offering.selected { border-color: #6c5ce7; box-shadow: 0 10rpx 30rpx rgba(108,92,231,.08); }
.check { width: 36rpx; height: 36rpx; border-radius: 50%; border: 2rpx solid #d7d6df; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18rpx; }
.selected .check { border-color: #6c5ce7; background: #6c5ce7; }
.offering-main { flex: 1; min-width: 0; }
.offering-name { font-size: 25rpx; font-weight: 700; }
.offering-desc, .offering-meta { margin-top: 8rpx; color: #92929d; font-size: 20rpx; }
.price { color: #6c5ce7; font-size: 29rpx; font-weight: 800; }
.section-card, .review, .empty { margin-top: 20rpx; padding: 28rpx; border-radius: 28rpx; background: #fff; }
.quantity-card { display:flex; align-items:center; justify-content:space-between; gap:20rpx; }
.section-title.compact { margin-bottom:0; }
.quantity-hint { margin-top:7rpx; color:#92929d; font-size:18rpx; }
.stepper { display:flex; align-items:center; gap:18rpx; }
.stepper button { margin:0; width:58rpx; height:58rpx; line-height:58rpx; padding:0; border-radius:18rpx; background:#f0edff; color:#6c5ce7; font-size:28rpx; }
.stepper button[disabled] { opacity:.35; }
.stepper text { min-width:34rpx; text-align:center; font-size:27rpx; font-weight:800; }
.section-card textarea { width: 100%; height: 140rpx; margin-top: 10rpx; font-size: 23rpx; }
.optional { color: #aaaab4; font-size: 20rpx; font-weight: 400; }
.review-rating { color: #f0b72f; font-size: 25rpx; }
.review-content { margin-top: 10rpx; color: #686872; font-size: 22rpx; line-height: 1.6; }
.empty { color: #92929d; text-align: center; font-size: 22rpx; }
.footer { position: fixed; left: 0; right: 0; bottom: 0; padding: 20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom)); display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,.97); border-top: 1rpx solid #ececf2; }
.footer-label { display: block; color: #92929d; font-size: 20rpx; }
.footer-price { display: block; margin-top: 4rpx; font-size: 34rpx; font-weight: 800; }
.buy { margin: 0; width: 300rpx; height: 84rpx; line-height: 84rpx; border-radius: 25rpx; background: #6c5ce7; color: #fff; font-size: 26rpx; font-weight: 700; }
.buy[disabled] { opacity: .45; }
</style>
