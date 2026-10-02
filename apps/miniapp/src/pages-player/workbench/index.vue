<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import { isWeChatAuthMode } from "../../api/config"
import SampleJourney from "../../components/SampleJourney.vue"\nimport UiButton from "../../components/ui/UiButton.vue"
import {
  getPlayerProfile,
  listPlayerOrders,
  updatePlayerServiceStatus,
  type PlayerProfile
} from "../../domain/player/api"
import { getWallet } from "../../domain/wallet/api"
import { navigation } from "../../platform/navigation"
import {
  getPlayerPrincipal,
  type ProductPrincipal
} from "../../product/principal"
import { useAsyncStatus } from "../../shared/composables/useAsyncStatus"
import type { Order, Wallet } from "../../types/domain"
import { showMessage } from "../../ui/feedback"
import OfferingPanel from "./OfferingPanel.vue"
import SkillPanel from "./SkillPanel.vue"

const profile = ref<PlayerProfile | null>(null)
const wallet = ref<Wallet>({ availableBalance: 0, frozenBalance: 0 })
const orders = ref<Order[]>([])
const principal = ref<ProductPrincipal | null>(null)
const busy = ref(false)
const refreshing = ref(false)
const serviceSettingsOpen = ref(false)
const demoMode = !isWeChatAuthMode()
const {
  status: loadStatus,
  message: loadMessage,
  start: startLoad,
  succeed: finishLoad,
  fail: failLoad
} = useAsyncStatus()

const online = computed(() => profile.value?.service_status === "AVAILABLE")
const verified = computed(() => profile.value?.verification_status === "APPROVED")
const acceptedCount = computed(() =>
  orders.value.filter(item => item.status === "ACCEPTED").length
)
const inServiceCount = computed(() =>
  orders.value.filter(item => item.status === "IN_SERVICE").length
)
const waitingConfirmCount = computed(() =>
  orders.value.filter(item => item.status === "FINISH_REQUESTED").length
)
const activeIncome = computed(() =>
  orders.value
    .filter(item =>
      ["ACCEPTED", "IN_SERVICE", "FINISH_REQUESTED"].includes(item.status)
    )
    .reduce((sum, item) => sum + item.player_amount, 0)
)

async function load() {
  const hasContent = Boolean(profile.value)
  if (hasContent) refreshing.value = true
  else startLoad()

  try {
    const nextPrincipal = await getPlayerPrincipal()
    if (!nextPrincipal) {
      principal.value = null
      profile.value = null
      orders.value = []
      wallet.value = { availableBalance: 0, frozenBalance: 0 }
      finishLoad({ empty: true })
      return
    }

    const [nextProfile, nextWallet, nextOrders] = await Promise.all([
      getPlayerProfile(nextPrincipal),
      getWallet(nextPrincipal),
      listPlayerOrders(nextPrincipal)
    ])

    principal.value = nextPrincipal
    profile.value = nextProfile
    wallet.value = nextWallet
    orders.value = nextOrders
    finishLoad()
  } catch (error) {
    if (hasContent) {
      showMessage(error instanceof Error ? error.message : "工作台刷新失败")
    } else {
      failLoad(error, "陪玩工作台加载失败")
    }
  } finally {
    refreshing.value = false
  }
}

async function toggleStatus() {
  if (!profile.value || !principal.value || busy.value) return
  if (!verified.value) {
    showMessage("认证通过后才能开启接单")
    return
  }

  busy.value = true
  try {
    profile.value = await updatePlayerServiceStatus(
      principal.value,
      online.value ? "OFFLINE" : "AVAILABLE"
    )
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "状态切换失败")
  } finally {
    busy.value = false
  }
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
        <text class="eyebrow">陪玩中心</text>
        <text class="title">{{ profile?.display_name || "陪玩工作台" }}</text>
      </view>
      <view
        v-if="profile"
        class="availability"
        :class="{ off: !online, disabled: !verified }"
        @click="toggleStatus"
      >
        <text class="pulse"></text>
        {{ !verified ? "待认证" : online ? "正在接单" : "暂停接单" }}
      </view>
      <text v-else-if="refreshing" class="refreshing">刷新中</text>
    </view>

    <view v-if="loadStatus === 'loading'" class="loading-stack">
      <view class="skeleton-dark hero-skeleton"></view>
      <view class="skeleton-grid">
        <view class="skeleton-dark action-skeleton"></view>
        <view class="skeleton-dark action-skeleton"></view>
      </view>
    </view>

    <view
      v-else-if="loadStatus === 'error'"
      class="state-card"
    >
      <text class="state-symbol">↻</text>
      <text class="state-title">工作台暂时没加载出来</text>
      <text class="state-description">{{ loadMessage }}</text>
      <view class="state-action">
        <UiButton size="sm" variant="secondary" inverse @click="load">
          重新加载
        </UiButton>
      </view>
    </view>

    <view
      v-else-if="loadStatus === 'empty'"
      class="state-card"
    >
      <text class="state-symbol">陪</text>
      <text class="state-title">当前账号还不是陪玩</text>
      <text class="state-description">
        完成陪玩身份申请并通过认证后，这里会展示接单与收益工作台。
      </text>
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
        <text class="money-label">可用收益</text>
        <view class="money-row">
          <text class="currency">¥</text>
          <text class="amount">{{ (wallet.availableBalance / 100).toFixed(2) }}</text>
        </view>
        <view class="money-bottom">
          <text>冻结 ¥{{ (wallet.frozenBalance / 100).toFixed(2) }}</text>
          <text class="earnings-link" @click="openWithdrawals">收益与提现 ›</text>
        </view>
      </view>

      <view class="action-grid">
        <view class="action-card primary" @click="openPool">
          <view class="action-icon">抢</view>
          <text class="action-title">去抢单</text>
          <text class="action-desc">查看当前可接服务</text>
          <text class="action-arrow">›</text>
        </view>
        <view class="action-card" @click="openOrders">
          <view class="action-icon muted">单</view>
          <text class="action-title">服务订单</text>
          <text class="action-desc">开始、完成与历史订单</text>
          <text class="action-arrow">›</text>
        </view>
      </view>

      <view class="section-title-row">
        <text class="section-title">当前履约</text>
        <text class="section-note">
          预计收入 ¥{{ (activeIncome / 100).toFixed(2) }}
        </text>
      </view>
      <view class="stats">
        <view><b>{{ acceptedCount }}</b><text>待开始</text></view>
        <view><b>{{ inServiceCount }}</b><text>服务中</text></view>
        <view><b>{{ waitingConfirmCount }}</b><text>待确认</text></view>
      </view>

      <view
        class="settings-entry"
        @click="serviceSettingsOpen = !serviceSettingsOpen"
      >
        <view class="settings-icon">设</view>
        <view class="settings-main">
          <text class="settings-title">我的服务</text>
          <text class="settings-desc">服务套餐与技能认证</text>
        </view>
        <text class="settings-arrow">
          {{ serviceSettingsOpen ? "⌃" : "›" }}
        </text>
      </view>

      <template v-if="serviceSettingsOpen">
        <OfferingPanel
          v-if="principal"
          :user-id="principal.userId"
        />
        <SkillPanel
          v-if="principal"
          :user-id="principal.userId"
        />
      </template>
    </template>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;padding-bottom:calc(42rpx + env(safe-area-inset-bottom));background:var(--inverse-bg);color:#fff}
.work-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;padding:10rpx 2rpx 24rpx}.eyebrow,.title{display:block}.eyebrow{color:#706e7c;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;font-size:36rpx;font-weight:850}.refreshing{padding-bottom:5rpx;color:#777582;font-size:17rpx}
.availability{display:flex;align-items:center;gap:8rpx;padding:10rpx 14rpx;border-radius:999rpx;background:rgba(39,187,111,.11);color:#62d895;font-size:18rpx;font-weight:700}.availability.off{background:rgba(255,255,255,.06);color:#8b8995}.availability.disabled{background:rgba(211,148,38,.11);color:#d9ad5e}.pulse{width:11rpx;height:11rpx;border-radius:50%;background:currentColor}
.loading-stack{display:flex;flex-direction:column;gap:18rpx}.skeleton-grid{display:grid;grid-template-columns:1fr 1fr;gap:13rpx}.skeleton-dark{position:relative;overflow:hidden;background:var(--inverse-surface);border:1rpx solid rgba(255,255,255,.04)}.skeleton-dark::after{content:"";position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,rgba(255,255,255,.055),transparent);animation:shimmer 1.4s infinite}.hero-skeleton{height:210rpx;border-radius:34rpx}.action-skeleton{height:190rpx;border-radius:29rpx}@keyframes shimmer{100%{transform:translateX(100%)}}
.state-card{padding:58rpx 34rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:32rpx;background:var(--inverse-surface);text-align:center}.state-symbol{width:82rpx;height:82rpx;margin:0 auto;display:flex;align-items:center;justify-content:center;border-radius:26rpx;background:var(--inverse-control-strong);color:var(--brand-on-inverse);font-size:28rpx;font-weight:800}.state-title{display:block;margin-top:20rpx;font-size:27rpx;font-weight:780}.state-description{display:block;max-width:520rpx;margin:10rpx auto 0;color:#777582;font-size:19rpx;line-height:1.55}.state-action{display:flex;justify-content:center;margin-top:24rpx}
.money-card{position:relative;overflow:hidden;padding:30rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:34rpx;background:linear-gradient(145deg,#1b1a23,#272337);box-shadow:0 22rpx 60rpx rgba(0,0,0,.16)}.money-label{color:#8e8c99;font-size:19rpx}.money-row{display:flex;align-items:baseline;margin-top:8rpx}.currency{color:#b8aef7;font-size:24rpx;font-weight:750}.amount{margin-left:4rpx;font-size:52rpx;font-weight:850;letter-spacing:-1rpx}.money-bottom{display:flex;justify-content:space-between;gap:18rpx;margin-top:23rpx;padding-top:19rpx;border-top:1rpx solid rgba(255,255,255,.06);color:#777582;font-size:18rpx}.earnings-link{color:var(--brand-on-inverse);font-weight:700}
.action-grid{display:grid;grid-template-columns:1fr 1fr;gap:13rpx;margin-top:18rpx}.action-card{position:relative;min-height:190rpx;padding:23rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:29rpx;background:var(--inverse-surface)}.action-card.primary{background:linear-gradient(145deg,var(--brand),#5846cc);border-color:transparent}.action-icon{width:48rpx;height:48rpx;display:flex;align-items:center;justify-content:center;border-radius:16rpx;background:rgba(255,255,255,.14);font-size:18rpx;font-weight:850}.action-icon.muted{background:var(--inverse-control-strong);color:#aaa8b5}.action-title,.action-desc{display:block}.action-title{margin-top:20rpx;font-size:25rpx;font-weight:800}.action-desc{margin-top:6rpx;color:rgba(255,255,255,.58);font-size:17rpx;line-height:1.45}.action-card:not(.primary) .action-desc{color:#777582}.action-arrow{position:absolute;right:21rpx;top:20rpx;color:rgba(255,255,255,.45);font-size:28rpx}
.section-title-row{display:flex;align-items:center;justify-content:space-between;margin:30rpx 2rpx 14rpx}.section-title{font-size:24rpx;font-weight:780}.section-note{color:#777582;font-size:17rpx}
.stats{display:flex;gap:10rpx}.stats view{flex:1;padding:20rpx 8rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:22rpx;background:var(--inverse-surface);text-align:center}.stats b,.stats text{display:block}.stats b{font-size:28rpx}.stats text{margin-top:5rpx;color:#777582;font-size:16rpx}
.settings-entry{display:flex;align-items:center;gap:17rpx;margin-top:18rpx;padding:23rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:26rpx;background:var(--inverse-surface)}.settings-icon{width:48rpx;height:48rpx;display:flex;align-items:center;justify-content:center;border-radius:16rpx;background:var(--inverse-control-strong);color:#9895a5;font-size:18rpx;font-weight:800}.settings-main{flex:1}.settings-title,.settings-desc{display:block}.settings-title{font-size:23rpx;font-weight:760}.settings-desc{margin-top:5rpx;color:#777582;font-size:17rpx}.settings-arrow{color:#676572;font-size:30rpx}
</style>
