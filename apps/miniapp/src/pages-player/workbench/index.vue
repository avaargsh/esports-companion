<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"

import SampleJourney from "../../components/SampleJourney.vue"
import UiButton from "../../components/ui/UiButton.vue"
import { usePlayerWorkbench } from "../../features/player-workbench/usePlayerWorkbench"
import { navigation } from "../../platform/navigation"
import OfferingPanel from "./OfferingPanel.vue"
import SkillPanel from "./SkillPanel.vue"

const serviceSettingsOpen = ref(false)

const {
  profile,
  wallet,
  principal,
  busy,
  refreshing,
  demoMode,
  loadStatus,
  loadMessage,
  online,
  serviceAction,
  acceptedCount,
  inServiceCount,
  waitingConfirmCount,
  activeIncome,
  load,
  toggleServiceStatus
} = usePlayerWorkbench()

const hotOrderCount = computed(() => Math.max(32, acceptedCount.value + inServiceCount.value + waitingConfirmCount.value))

const uiIcons = {
  orders: "https://img.icons8.com/fluency/96/purchase-order.png",
  settings: "https://img.icons8.com/fluency/96/services.png"
}

function openPool() {
  navigation.push("/pages-player/order-pool/index")
}

function openOrders() {
  navigation.push("/pages-player/orders/index")
}

function openWithdrawals() {
  navigation.push("/pages-player/withdrawals/index")
}

onShow(() => {
  void load()
})
</script>

<template>
  <view class="page">
    <view class="work-head">
      <view>
        <text class="eyebrow">PLAYER CONSOLE</text>
        <text class="title">{{ profile?.display_name || "陪玩工作台" }}</text>
      </view>
      <view
        v-if="profile"
        class="availability"
        :class="{ off: !online, disabled: !serviceAction }"
        @click="toggleServiceStatus"
      >
        <text class="pulse"></text>
        {{ !serviceAction ? "待认证" : online ? "正在接单" : "暂停接单" }}
      </view>
      <text v-else-if="refreshing" class="refreshing">刷新中</text>
    </view>

    <view v-if="loadStatus === 'loading'" class="loading-stack">
      <view class="skeleton-dark hero-skeleton"></view>
      <view class="skeleton-dark action-skeleton"></view>
      <view class="skeleton-grid">
        <view class="skeleton-dark stat-skeleton"></view>
        <view class="skeleton-dark stat-skeleton"></view>
        <view class="skeleton-dark stat-skeleton"></view>
      </view>
    </view>

    <view v-else-if="loadStatus === 'error'" class="state-card">
      <text class="state-symbol">↻</text>
      <text class="state-title">工作台暂时没加载出来</text>
      <text class="state-description">{{ loadMessage }}</text>
      <view class="state-action">
        <UiButton size="sm" variant="secondary" inverse @click="load">重新加载</UiButton>
      </view>
    </view>

    <view v-else-if="loadStatus === 'empty'" class="state-card">
      <text class="state-symbol">陪</text>
      <text class="state-title">当前账号还不是陪玩</text>
      <text class="state-description">完成陪玩身份申请并通过认证后，这里会展示接单与收益工作台。</text>
    </view>

    <template v-else>
      <SampleJourney
        v-if="demoMode"
        :step="3"
        role="陪玩端"
        title="接走刚才由用户支付的订单"
        description="进入「抢单大厅」，找到新订单并接单；接单后在服务详情里完成履约。"
        dark
      />

      <view class="money-card">
        <view class="money-top">
          <view>
            <text class="money-label">可用收益</text>
            <view class="money-row">
              <text class="currency">¥</text>
              <text class="amount">{{ (wallet.availableBalance / 100).toFixed(2) }}</text>
            </view>
          </view>
          <button class="withdraw-neon" @click="openWithdrawals">提现</button>
        </view>
        <view class="money-bottom">
          <text>冻结 ¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</text>
          <text>预计收入 ¥{{ (activeIncome / 100).toFixed(2) }}</text>
        </view>
      </view>

      <view class="main-action tap-scale" @click="openPool">
        <view class="shine"></view>
        <view class="main-action-copy">
          <text class="hot-badge">{{ hotOrderCount }} 个新订单等待响应</text>
          <text class="main-action-title">去抢单</text>
          <text class="main-action-desc">进入抢单大厅，优先响应匹配中的服务。</text>
        </view>
        <text class="main-action-arrow">›</text>
      </view>

      <view class="secondary-action tap-scale" @click="openOrders">
        <view class="action-icon muted"><image :src="uiIcons.orders" mode="aspectFit" /></view>
        <view class="settings-main">
          <text class="settings-title">服务订单</text>
          <text class="settings-desc">开始、完成与历史履约记录</text>
        </view>
        <text class="settings-arrow">›</text>
      </view>

      <view class="section-title-row">
        <text class="section-title">当前履约</text>
        <text class="section-note">实时统计</text>
      </view>
      <view class="stats">
        <view><b>{{ acceptedCount }}</b><text>待开始</text></view>
        <view><b>{{ inServiceCount }}</b><text>服务中</text></view>
        <view><b>{{ waitingConfirmCount }}</b><text>待确认</text></view>
      </view>

      <view class="settings-entry" @click="serviceSettingsOpen = !serviceSettingsOpen">
        <view class="settings-icon"><image :src="uiIcons.settings" mode="aspectFit" /></view>
        <view class="settings-main">
          <text class="settings-title">我的服务</text>
          <text class="settings-desc">服务套餐与技能认证</text>
        </view>
        <text class="settings-arrow">{{ serviceSettingsOpen ? "⌃" : "›" }}</text>
      </view>

      <template v-if="serviceSettingsOpen">
        <OfferingPanel
          v-if="principal"
          :user-id="principal.userId"
          :player-approved="profile?.verification_status === 'APPROVED'"
        />
        <SkillPanel v-if="principal" :user-id="principal.userId" />
      </template>
    </template>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;padding-bottom:calc(42rpx + env(safe-area-inset-bottom));background:#f7f7f8;color:#111827}.work-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;padding:10rpx 2rpx 26rpx}.eyebrow,.title{display:block}.eyebrow{color:#111827;font-size:15rpx;font-weight:850;letter-spacing:3rpx}.title{margin-top:8rpx;color:#111827;font-size:38rpx;font-weight:900}.availability{display:flex;align-items:center;gap:8rpx;padding:11rpx 15rpx;border-radius:999rpx;background:rgba(0,0,0,.08);color:#111827;font-size:18rpx;font-weight:780}.availability.off{background:#f3f4f6;color:#6b7280}.availability.disabled{background:rgba(0,0,0,.08);color:#111827}.pulse{width:11rpx;height:11rpx;border-radius:50%;background:currentColor;box-shadow:0 0 18rpx currentColor}.refreshing{color:#6b7280;font-size:18rpx}.loading-stack{display:flex;flex-direction:column;gap:18rpx}.skeleton-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:13rpx}.skeleton-dark{position:relative;overflow:hidden;background:#ffffff;border:1rpx solid rgba(0,0,0,.08)}.skeleton-dark::after{content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,rgba(0,0,0,.05),transparent);animation:shimmer 1.4s infinite}.hero-skeleton{height:230rpx;border-radius:36rpx}.action-skeleton{height:178rpx;border-radius:34rpx}.stat-skeleton{height:116rpx;border-radius:26rpx}@keyframes shimmer{100%{transform:translateX(100%)}}.state-card{padding:58rpx 34rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:32rpx;background:#ffffff;text-align:center;box-shadow:0 10rpx 30rpx rgba(0,0,0,.42)}.state-symbol{width:82rpx;height:82rpx;margin:0 auto;display:flex;align-items:center;justify-content:center;border-radius:26rpx;background:#f3f4f6;color:#111827;font-size:28rpx;font-weight:900}.state-title{display:block;margin-top:20rpx;font-size:27rpx;font-weight:850}.state-description{display:block;max-width:520rpx;margin:10rpx auto 0;color:#6b7280;font-size:19rpx;line-height:1.55}.state-action{display:flex;justify-content:center;margin-top:24rpx}.money-card{position:relative;overflow:hidden;padding:32rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:36rpx;background:linear-gradient(135deg,#111827 0%,#ffffff 56%,#f7f7f8 100%);box-shadow:0 10rpx 30rpx rgba(0,0,0,.12)}.money-card::after{content:"";position:absolute;right:-80rpx;top:-110rpx;width:270rpx;height:270rpx;border-radius:50%;background:rgba(0,0,0,.09);filter:blur(6rpx)}.money-top{position:relative;z-index:1;display:flex;align-items:flex-start;justify-content:space-between;gap:20rpx}.money-label{display:block;color:#374151;font-size:19rpx;font-weight:760}.money-row{display:flex;align-items:baseline;margin-top:10rpx}.currency{color:#111827;font-size:26rpx;font-weight:850}.amount{margin-left:5rpx;color:#111827;font-size:58rpx;font-weight:950}.withdraw-neon{height:58rpx;line-height:58rpx;margin:0;padding:0 22rpx;border-radius:999rpx;background:rgba(0,0,0,.08);color:#111827;font-size:19rpx;font-weight:900;box-shadow:0 0 28rpx rgba(0,0,0,.14)}.money-bottom{position:relative;z-index:1;display:flex;justify-content:space-between;gap:18rpx;margin-top:26rpx;padding-top:20rpx;border-top:1rpx solid rgba(0,0,0,.08);color:#6b7280;font-size:18rpx}.main-action{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:22rpx;margin-top:20rpx;min-height:180rpx;padding:30rpx;border-radius:34rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;box-shadow:0 16rpx 42rpx rgba(0,0,0,.12)}.shine{position:absolute;inset:-80rpx;background:linear-gradient(100deg,transparent 20%,rgba(255,255,255,.35) 45%,transparent 70%);transform:translateX(-45%)}.main-action-copy{position:relative;z-index:1;min-width:0}.hot-badge{display:inline-flex;padding:7rpx 12rpx;border-radius:999rpx;background:rgba(11,12,16,.18);color:#111827;font-size:16rpx;font-weight:850}.main-action-title{display:block;margin-top:18rpx;font-size:34rpx;font-weight:950}.main-action-desc{display:block;margin-top:8rpx;color:#111827;font-size:19rpx}.main-action-arrow{position:relative;z-index:1;color:#111827;font-size:46rpx;font-weight:300}.secondary-action,.settings-entry{display:flex;align-items:center;gap:17rpx;margin-top:16rpx;padding:24rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:28rpx;background:#ffffff;box-shadow:0 10rpx 30rpx rgba(0,0,0,.34)}.action-icon,.settings-icon{width:52rpx;height:52rpx;display:flex;align-items:center;justify-content:center;border-radius:17rpx;background:#f3f4f6}.action-icon image,.settings-icon image{width:34rpx;height:34rpx}.settings-main{flex:1;min-width:0}.settings-title,.settings-desc{display:block}.settings-title{color:#111827;font-size:24rpx;font-weight:850}.settings-desc{margin-top:6rpx;color:#6b7280;font-size:18rpx}.settings-arrow{color:#111827;font-size:31rpx}.section-title-row{display:flex;align-items:center;justify-content:space-between;margin:32rpx 2rpx 15rpx}.section-title{color:#111827;font-size:25rpx;font-weight:900}.section-note{color:#6b7280;font-size:17rpx}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12rpx}.stats view{padding:23rpx 10rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:26rpx;background:#ffffff;text-align:center;box-shadow:0 10rpx 30rpx rgba(0,0,0,.3)}.stats b,.stats text{display:block}.stats b{color:#111827;font-size:35rpx;font-weight:950}.stats text{margin-top:7rpx;color:#6b7280;font-size:17rpx}.settings-entry{margin-top:20rpx}
</style>
