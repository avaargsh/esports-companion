<script setup lang="ts">
import { computed } from "vue"
import { onShow } from "@dcloudio/uni-app"

import SampleJourney from "../../components/SampleJourney.vue"
import {
  useProfileIdentity,
  type PhoneNumberEvent
} from "../../features/profile/useProfileIdentity"
import { requireLoginPrompt } from "../../features/profile/authGuard"
import { navigation } from "../../platform/navigation"
import { showMessage, showSuccess } from "../../ui/feedback"

const {
  wechatMode,
  loggedIn,
  phoneBusy,
  nickname,
  avatarUrl,
  phone,
  phoneText,
  userId,
  role,
  playerName,
  playerProfile,
  playerChecked,
  applyOpen,
  applyName,
  applyBio,
  applying,
  loadIdentity,
  logout,
  bindPhone,
  submitApplication
} = useProfileIdentity()

const uiIcons = {
  studio: "https://img.icons8.com/fluency/96/joystick.png",
  profile: "https://img.icons8.com/fluency/96/user-male-circle.png",
  orders: "https://img.icons8.com/fluency/96/purchase-order.png",
  apply: "https://img.icons8.com/fluency/96/approval.png",
  rejected: "https://img.icons8.com/fluency/96/cancel.png",
  pending: "https://img.icons8.com/fluency/96/time-machine.png",
  support: "https://img.icons8.com/fluency/96/help.png"
}

const canOpenPlayerSystem = computed(() =>
  loggedIn.value &&
  (!wechatMode ||
    role.value === "PLATFORM" ||
    playerProfile.value?.verification_status === "APPROVED")
)

const playerSystemDescription = computed(() => {
  if (role.value === "PLATFORM") return "平台管理员 · 陪玩系统已开放"
  return playerName.value
    ? playerName.value + " · 接单、履约与收益"
    : "进入陪玩工作台"
})

async function openPlayerWorkspace() {
  if (!loggedIn.value) {
    await requireLoginPrompt()
    return
  }
  if (!canOpenPlayerSystem.value) return
  navigation.push("/pages-player/workbench/index")
}

async function openOrders() {
  if (!(await requireLoginPrompt())) return
  navigation.tab("/pages/orders/index")
}

async function openProfileInfo() {
  if (!(await requireLoginPrompt())) return
  navigation.push("/pages/profile-info/index")
}

async function openLoginPrompt() {
  await requireLoginPrompt()
}

async function onGetPhoneNumber(event: PhoneNumberEvent) {
  if (!(await requireLoginPrompt())) return
  void bindPhone(event)
}

function copyValue(value: string, label: string) {
  if (!value) {
    showMessage(label + "暂无内容")
    return
  }
  uni.setClipboardData({
    data: value,
    success() {
      showSuccess("已复制" + label)
    }
  })
}

onShow(() => {
  void loadIdentity()
})
</script>

<template>
  <view class="safe-page custom-safe-page profile-page">
    <view class="heading">
      <text class="title">我的</text>
      <text class="subtitle">账号、订单和服务入口都在这里。</text>
    </view>

    <SampleJourney
      v-if="!wechatMode"
      :step="2"
      title="支付后，从这里切到陪玩端"
      description="进入「陪玩工作台」→「抢单大厅」，找到刚才由用户支付的订单并接单。"
    />

    <view class="identity-card">
      <view class="avatar-ring">
        <image v-if="avatarUrl" class="avatar-image" :src="avatarUrl" mode="aspectFill" />
        <view v-else class="avatar">{{ (nickname || "微").slice(0, 1).toUpperCase() }}</view>
      </view>
      <view class="identity-main">
        <view class="name-row">
          <text class="name">{{ loggedIn ? (nickname || "微信用户") : "未登录" }}</text>
          <text v-if="loggedIn" class="verified">已认证</text>
        </view>
        <text class="hint">{{ loggedIn ? "微信身份已连接" : "登录后同步订单和个人资料" }}</text>
      </view>
      <view :class="['identity-badge', { off: !loggedIn }]">{{ loggedIn ? "在线" : "离线" }}</view>
    </view>

    <view v-if="wechatMode" class="account-actions">
      <button v-if="!loggedIn" class="primary-action" @click="openLoginPrompt">立即登录</button>
      <template v-else>
        <button class="primary-action" @click="openProfileInfo">个人信息</button>
        <button class="secondary-action" :loading="phoneBusy" open-type="getPhoneNumber" @getphonenumber="onGetPhoneNumber">{{ phoneText }}</button>
        <button class="logout-action" @click="logout">退出登录</button>
      </template>
    </view>

    <view v-if="wechatMode && loggedIn" class="secure-info">
      <view class="secure-row" @click="copyValue(phone, '手机号')">
        <text>手机号</text><b>{{ phone ? phone.slice(0, 3) + '****' + phone.slice(-4) : '未绑定' }}</b>
      </view>
      <view class="secure-row">
        <text>身份</text><b>{{ role === "PLATFORM" ? "平台管理员" : "普通用户" }}</b>
      </view>
      <view class="secure-row" @click="copyValue(userId, '用户 ID')">
        <text>User ID</text><b>{{ userId.slice(0, 8) || "-" }}</b>
      </view>
    </view>

    <view
      v-if="canOpenPlayerSystem || !loggedIn"
      class="studio-banner tap-scale"
      @click="openPlayerWorkspace"
    >
      <view class="studio-left">
        <view class="studio-mark"><image :src="uiIcons.studio" mode="aspectFit" /></view>
        <view>
          <text class="studio-kicker">陪玩工作室</text>
          <text class="studio-title">接单中心</text>
          <text class="studio-desc">{{ loggedIn ? playerSystemDescription : "登录后进入接单中心" }}</text>
        </view>
      </view>
      <view class="studio-action">立即进入 ›</view>
    </view>

    <view v-else-if="loggedIn && role !== 'PLATFORM' && playerChecked && playerProfile?.verification_status === 'PENDING'" class="status-card pending">
      <view class="status-icon"><image :src="uiIcons.pending" mode="aspectFit" /></view>
      <view>
        <text class="status-title">陪玩申请审核中</text>
        <text class="status-desc">{{ playerProfile.display_name }} · 审核通过后自动开放工作台。</text>
      </view>
    </view>

    <view v-else-if="loggedIn && role !== 'PLATFORM' && playerChecked && playerProfile?.verification_status === 'REJECTED'" class="status-card rejected">
      <view class="status-icon"><image :src="uiIcons.rejected" mode="aspectFit" /></view>
      <view>
        <text class="status-title">陪玩申请未通过</text>
        <text class="status-desc">用户下单不受影响，需要时可联系平台重新审核。</text>
      </view>
    </view>

    <view v-else-if="wechatMode && loggedIn && role !== 'PLATFORM' && playerChecked" class="apply-card">
      <view v-if="!applyOpen" class="apply-entry tap-scale" @click="applyOpen = true">
        <view class="apply-icon"><image :src="uiIcons.apply" mode="aspectFit" /></view>
        <view class="apply-main">
          <text class="apply-title">想成为陪玩？</text>
          <text class="apply-desc">提交必要资料，审核通过后开启接单。</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <template v-else>
        <view class="apply-head">
          <view>
            <text class="apply-title">申请成为陪玩</text>
            <text class="apply-desc">先填写昵称和一句自我介绍。</text>
          </view>
          <text class="close" @click="applyOpen = false">取消</text>
        </view>
        <input v-model="applyName" maxlength="80" placeholder="陪玩昵称" />
        <textarea v-model="applyBio" maxlength="500" placeholder="简单介绍自己，可选" />
        <button class="apply-button" :loading="applying" @click="submitApplication">提交申请</button>
      </template>
    </view>

    <view class="menu-card">
      <view v-if="wechatMode" class="menu-item tap-scale" @click="openProfileInfo">
        <view class="duotone cyan"><image :src="uiIcons.profile" mode="aspectFit" /></view>
        <view class="menu-main"><text class="menu-title">个人信息</text><text class="menu-desc">头像、昵称和手机号</text></view>
        <text class="arrow">›</text>
      </view>
      <view class="menu-item tap-scale" @click="openOrders">
        <view class="duotone violet"><image :src="uiIcons.orders" mode="aspectFit" /></view>
        <view class="menu-main"><text class="menu-title">我的订单</text><text class="menu-desc">进行中的服务、历史订单与售后</text></view>
        <text class="arrow">›</text>
      </view>
    </view>

    <view v-if="!loggedIn && wechatMode" class="login-note">登录后可以查看订单、绑定手机号、申请陪玩身份。</view>
    <view class="support-note"><view class="support-icon"><image :src="uiIcons.support" mode="aspectFit" /></view><text>退款、争议和联系陪玩都从对应订单详情进入，处理路径更清晰。</text></view>
  </view>
</template>

<style scoped>
.profile-page{min-height:100vh;padding-top:24rpx;background:#f7f7f8;color:#111827}.heading{padding:8rpx 3rpx 24rpx}.title{display:block;color:#111827;font-size:40rpx;font-weight:900}.subtitle{display:block;margin-top:8rpx;color:#6b7280;font-size:20rpx}.identity-card{display:flex;align-items:center;gap:20rpx;padding:28rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:34rpx;background:linear-gradient(145deg,#ffffff,#f3f4f6);box-shadow:0 10rpx 30rpx rgba(0,0,0,.12)}.avatar-ring{width:104rpx;height:104rpx;flex:none;padding:5rpx;border-radius:34rpx;background:linear-gradient(135deg,#111827,#000000);box-shadow:0 0 28rpx rgba(0,0,0,.16)}.avatar,.avatar-image{width:100%;height:100%;border-radius:29rpx}.avatar{display:flex;align-items:center;justify-content:center;background:#f7f7f8;color:#111827;font-size:34rpx;font-weight:900}.avatar-image{display:block;background:#f3f4f6}.identity-main{flex:1;min-width:0}.name-row{display:flex;align-items:center;gap:10rpx;min-width:0}.name{overflow:hidden;color:#111827;font-size:30rpx;font-weight:900;text-overflow:ellipsis;white-space:nowrap}.verified{flex:none;padding:5rpx 10rpx;border-radius:999rpx;background:rgba(0,0,0,.08);color:#111827;font-size:14rpx;font-weight:850;box-shadow:0 0 18rpx rgba(0,0,0,.10)}.hint{display:block;margin-top:7rpx;color:#6b7280;font-size:19rpx}.identity-badge{flex:none;padding:7rpx 12rpx;border-radius:999rpx;background:rgba(0,0,0,.08);color:#111827;font-size:16rpx;font-weight:800}.identity-badge.off{background:#f3f4f6;color:#6b7280}.account-actions{display:grid;grid-template-columns:1fr 1fr;gap:14rpx;margin-top:18rpx;padding:18rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.account-actions .primary-action:only-child{grid-column:1/3}.primary-action,.secondary-action,.logout-action{height:78rpx;line-height:78rpx;margin:0;border-radius:23rpx;font-size:21rpx;font-weight:850}.primary-action{background:linear-gradient(135deg,#111827,#000000);color:#fff;box-shadow:0 14rpx 30rpx rgba(0,0,0,.14)}.secondary-action{background:#f3f4f6;color:#111827;border:1rpx solid rgba(0,0,0,.09)}.logout-action{grid-column:1/3;background:rgba(244,63,94,.12);color:#fb7185;border:1rpx solid rgba(244,63,94,.16)}.secure-info{display:grid;gap:12rpx;margin-top:18rpx}.secure-row{display:flex;align-items:center;justify-content:space-between;gap:20rpx;padding:20rpx 24rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:24rpx;background:#ffffff;color:#6b7280;font-size:18rpx}.secure-row b{max-width:430rpx;overflow:hidden;color:#111827;font-size:20rpx;font-weight:850;text-overflow:ellipsis;white-space:nowrap}.studio-banner{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;gap:22rpx;margin-top:20rpx;padding:30rpx;border:1rpx solid rgba(0,0,0,.10);border-radius:34rpx;background:linear-gradient(135deg,#111827,#ffffff 54%,#f7f7f8);color:#fff;box-shadow:0 10rpx 30rpx rgba(0,0,0,.12)}.studio-banner::after{content:"";position:absolute;right:-70rpx;top:-90rpx;width:230rpx;height:230rpx;border-radius:50%;background:rgba(0,0,0,.09);filter:blur(4rpx)}.studio-left{position:relative;z-index:1;display:flex;align-items:center;gap:18rpx;min-width:0}.studio-mark{width:70rpx;height:70rpx;display:flex;align-items:center;justify-content:center;border-radius:23rpx;background:rgba(0,0,0,.08);box-shadow:0 0 28rpx rgba(0,0,0,.12)}.studio-mark image{width:44rpx;height:44rpx}.studio-kicker,.studio-title,.studio-desc{display:block}.studio-kicker{color:#111827;font-size:16rpx;font-weight:850}.studio-title{margin-top:5rpx;font-size:30rpx;font-weight:900}.studio-desc{margin-top:7rpx;color:#6b7280;font-size:18rpx}.studio-action{position:relative;z-index:1;flex:none;padding:13rpx 16rpx;border-radius:999rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;font-size:18rpx;font-weight:850}.menu-card{margin-top:20rpx;overflow:hidden;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.menu-item{display:flex;align-items:center;gap:18rpx;padding:26rpx;border-bottom:1rpx solid rgba(0,0,0,.06)}.menu-item:last-child{border-bottom:0}.duotone{width:58rpx;height:58rpx;display:flex;align-items:center;justify-content:center;border-radius:19rpx}.duotone image{width:36rpx;height:36rpx}.duotone.cyan{background:linear-gradient(135deg,rgba(0,0,0,.10),rgba(0,0,0,.06));color:#111827}.duotone.violet{background:linear-gradient(135deg,rgba(0,0,0,.10),rgba(0,0,0,.06));color:#111827}.menu-main{flex:1;min-width:0}.menu-title,.menu-desc{display:block}.menu-title{color:#111827;font-size:24rpx;font-weight:850}.menu-desc{margin-top:6rpx;color:#6b7280;font-size:18rpx}.arrow{flex:none;color:#6b7280;font-size:34rpx}.status-card{display:flex;gap:18rpx;align-items:center;margin-top:18rpx;padding:25rpx 27rpx;border-radius:28rpx}.pending{border:1rpx solid rgba(0,0,0,.10);background:rgba(0,0,0,.06);color:#111827}.rejected{border:1rpx solid rgba(244,63,94,.18);background:rgba(244,63,94,.1);color:#fb7185}.status-icon{width:52rpx;height:52rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:17rpx;background:rgba(0,0,0,.10)}.status-icon image{width:34rpx;height:34rpx}.status-title,.status-desc{display:block}.status-title{font-size:23rpx;font-weight:850}.status-desc{margin-top:6rpx;font-size:18rpx;line-height:1.5;opacity:.82}.apply-card{margin-top:18rpx;overflow:hidden;border:1rpx solid rgba(0,0,0,.08);border-radius:30rpx;background:#ffffff;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.apply-entry{display:flex;align-items:center;gap:18rpx;padding:26rpx}.apply-icon{width:58rpx;height:58rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:19rpx;background:rgba(0,0,0,.08)}.apply-icon image{width:36rpx;height:36rpx}.apply-main{flex:1}.apply-title,.apply-desc{display:block}.apply-title{color:#111827;font-size:24rpx;font-weight:850}.apply-desc{margin-top:6rpx;color:#6b7280;font-size:18rpx;line-height:1.5}.apply-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20rpx;padding:27rpx 28rpx 10rpx}.close{color:#6b7280;font-size:19rpx}.apply-card input,.apply-card textarea{width:calc(100% - 56rpx);margin:12rpx 28rpx 0;padding:19rpx;border-radius:19rpx;background:#f3f4f6;color:#111827;font-size:21rpx}.apply-card textarea{height:120rpx}.apply-button{margin:18rpx 28rpx 27rpx;height:78rpx;line-height:78rpx;border-radius:23rpx;background:linear-gradient(135deg,#111827,#000000);color:#fff;font-size:22rpx;font-weight:850}.login-note{margin-top:18rpx;padding:22rpx;border:1rpx solid rgba(0,0,0,.08);border-radius:24rpx;background:#ffffff;color:#6b7280;font-size:19rpx;line-height:1.55;box-shadow:0 12rpx 34rpx rgba(0,0,0,.08)}.support-note{display:flex;gap:13rpx;align-items:flex-start;margin-top:20rpx;padding:20rpx 22rpx;border:1rpx solid rgba(0,0,0,.06);border-radius:23rpx;background:#ffffff;color:#6b7280;font-size:18rpx;line-height:1.55}.support-icon{width:34rpx;height:34rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#f3f4f6}.support-icon image{width:24rpx;height:24rpx}
</style>
