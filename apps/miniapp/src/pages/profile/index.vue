<script setup lang="ts">
import { ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import { isWeChatAuthMode } from "../../api/config"
import { showSuccess, showMessage } from "../../ui/feedback"

type PlayerProfile={
  id:string
  user_id:string
  display_name:string
  bio:string
  verification_status:"PENDING"|"APPROVED"|"REJECTED"|string
  service_status:string
}
const wechatMode=isWeChatAuthMode()
const nickname=ref(wechatMode?"微信用户":"Demo Customer")
const userId=ref("")
const playerName=ref("")
const playerProfile=ref<PlayerProfile|null>(null)
const playerChecked=ref(!wechatMode)
const applyOpen=ref(false)
const applyName=ref("")
const applyBio=ref("")
const applying=ref(false)

async function loadIdentity(){
  try{
    const identities=await getDemoIdentities()
    userId.value=identities.customer.userId
    nickname.value=identities.customer.nickname||(wechatMode?"微信用户":"Demo Customer")
    if(!wechatMode){
      playerName.value=identities.players[0]?.displayName??""
      playerChecked.value=true
      return
    }
    try{
      playerProfile.value=await request<PlayerProfile>("/player/profile",{userId:userId.value})
      playerName.value=playerProfile.value.display_name
    }catch(error){
      const message=error instanceof Error?error.message:""
      if(message!=="PLAYER_PROFILE_NOT_FOUND")throw error
      playerProfile.value=null
      playerName.value=""
    }finally{playerChecked.value=true}
  }catch(error){
    showMessage(error instanceof Error?error.message:"账户加载失败")
  }
}
onShow(()=>{void loadIdentity()})
function openPlayerWorkspace(){
  if(wechatMode&&playerProfile.value?.verification_status!=="APPROVED")return
  uni.navigateTo({url:"/pages-player/workbench/index"})
}
function openOrders(){uni.switchTab({url:"/pages/orders/index"})}
async function applyPlayer(){
  if(!wechatMode||!userId.value||applying.value)return
  const displayName=applyName.value.trim()
  if(!displayName){showMessage("请填写陪玩昵称");return}
  applying.value=true
  try{
    playerProfile.value=await request<PlayerProfile>("/player/apply",{
      method:"POST",userId:userId.value,data:{display_name:displayName,bio:applyBio.value.trim()}
    })
    playerName.value=playerProfile.value.display_name
    applyOpen.value=false
    showSuccess("申请已提交")
  }catch(error){
    showMessage(error instanceof Error?error.message:"申请提交失败")
  }finally{applying.value=false}
}
</script>

<template>
  <view class="safe-page custom-safe-page profile-page">
    <view class="heading">
      <text class="title">我的</text>
      <text class="subtitle">订单、身份和服务入口都在这里。</text>
    </view>

    <view class="identity-card">
      <view class="avatar">{{ (nickname||"微").slice(0,1).toUpperCase() }}</view>
      <view class="identity-main">
        <text class="name">{{ nickname||"微信用户" }}</text>
        <text class="hint">{{ wechatMode ? "微信身份已连接" : "开发环境演示身份" }}</text>
      </view>
      <view class="identity-badge">已登录</view>
    </view>

    <view class="menu-card">
      <view class="menu-item tap-scale" @click="openOrders">
        <view class="menu-icon orders">单</view>
        <view class="menu-main">
          <text class="menu-title">我的订单</text>
          <text class="menu-desc">进行中的服务、历史订单与售后</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <view class="safe-row">
        <text>平台担保</text><text>·</text><text>完成后结算</text><text>·</text><text>订单内售后</text>
      </view>
    </view>

    <view
      v-if="!wechatMode || playerProfile?.verification_status==='APPROVED'"
      class="role-card tap-scale"
      @click="openPlayerWorkspace"
    >
      <view class="role-top">
        <view class="role-icon">P</view>
        <text class="role-badge">陪玩身份</text>
      </view>
      <text class="role-label">陪玩工作台</text>
      <text class="role-desc">{{ playerName ? playerName+" · 接单、履约与收益" : "进入陪玩工作台" }}</text>
      <text class="role-link">进入工作台 ›</text>
    </view>

    <view v-else-if="playerChecked&&playerProfile?.verification_status==='PENDING'" class="status-card pending">
      <view class="status-icon">审</view>
      <view>
        <text class="status-title">陪玩申请审核中</text>
        <text class="status-desc">{{ playerProfile.display_name }} · 审核通过后自动开放工作台。</text>
      </view>
    </view>

    <view v-else-if="playerChecked&&playerProfile?.verification_status==='REJECTED'" class="status-card rejected">
      <view class="status-icon">!</view>
      <view>
        <text class="status-title">陪玩申请未通过</text>
        <text class="status-desc">用户下单不受影响，需要时可联系平台重新审核。</text>
      </view>
    </view>

    <view v-else-if="wechatMode&&playerChecked" class="apply-card">
      <view v-if="!applyOpen" class="apply-entry tap-scale" @click="applyOpen=true">
        <view class="apply-icon">＋</view>
        <view class="apply-main">
          <text class="apply-title">想成为陪玩？</text>
          <text class="apply-desc">只提交必要资料，审核通过后再配置技能与服务。</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <template v-else>
        <view class="apply-head">
          <view>
            <text class="apply-title">申请成为陪玩</text>
            <text class="apply-desc">先填写昵称和一句自我介绍。</text>
          </view>
          <text class="close" @click="applyOpen=false">取消</text>
        </view>
        <input v-model="applyName" maxlength="80" placeholder="陪玩昵称" />
        <textarea v-model="applyBio" maxlength="500" placeholder="简单介绍自己，可选" />
        <button class="apply-button" :loading="applying" @click="applyPlayer">提交申请</button>
      </template>
    </view>

    <view class="support-note">
      <view class="support-icon">?</view>
      <text>退款、争议和联系陪玩都从对应订单详情进入，处理路径更清晰。</text>
    </view>
  </view>
</template>

<style scoped>
.profile-page{padding-top:24rpx}
.heading{padding:8rpx 3rpx 24rpx}.title{display:block;font-size:39rpx;font-weight:850;letter-spacing:-1rpx}.subtitle{display:block;margin-top:8rpx;color:var(--muted);font-size:20rpx}
.identity-card{display:flex;align-items:center;gap:20rpx;padding:28rpx;border-radius:32rpx;background:#fff;box-shadow:var(--shadow-card)}
.avatar{width:94rpx;height:94rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:29rpx;background:linear-gradient(145deg,#6757e6,#8977f3);color:#fff;font-size:34rpx;font-weight:850}
.identity-main{flex:1;min-width:0}.name{display:block;font-size:29rpx;font-weight:800}.hint{display:block;margin-top:7rpx;color:var(--muted);font-size:19rpx}
.identity-badge{flex:none;padding:7rpx 11rpx;border-radius:999rpx;background:var(--success-soft);color:var(--success);font-size:16rpx;font-weight:750}
.menu-card{margin-top:18rpx;overflow:hidden;border-radius:30rpx;background:#fff;box-shadow:var(--shadow-card)}
.menu-item{display:flex;align-items:center;gap:18rpx;padding:26rpx}
.menu-icon{width:58rpx;height:58rpx;display:flex;align-items:center;justify-content:center;border-radius:19rpx;font-size:21rpx;font-weight:850}.menu-icon.orders{background:var(--brand-soft);color:var(--brand)}
.menu-main{flex:1;min-width:0}.menu-title,.menu-desc{display:block}.menu-title{font-size:24rpx;font-weight:770}.menu-desc{margin-top:6rpx;color:var(--muted);font-size:18rpx}
.arrow{flex:none;color:#b7b7c0;font-size:34rpx}.safe-row{display:flex;justify-content:center;gap:9rpx;padding:17rpx;border-top:1rpx solid #f0f0f4;color:var(--muted-2);font-size:15rpx}
.role-card{position:relative;overflow:hidden;margin-top:18rpx;padding:28rpx;border-radius:32rpx;background:linear-gradient(145deg,#191821,#2b263f);color:#fff;box-shadow:0 18rpx 50rpx rgba(27,23,47,.16)}
.role-top{display:flex;align-items:center;gap:9rpx}.role-icon{width:42rpx;height:42rpx;display:flex;align-items:center;justify-content:center;border-radius:14rpx;background:#6757e6;font-size:18rpx;font-weight:850}.role-badge{color:#8f88a4;font-size:14rpx;font-weight:800;letter-spacing:2rpx}
.role-label{display:block;margin-top:24rpx;font-size:29rpx;font-weight:820}.role-desc{display:block;margin-top:7rpx;color:#a6a4b1;font-size:19rpx}.role-link{display:block;margin-top:20rpx;color:#b4a9ff;font-size:19rpx;font-weight:750}
.status-card{display:flex;gap:18rpx;align-items:center;margin-top:18rpx;padding:25rpx 27rpx;border-radius:28rpx}.pending{background:var(--brand-soft);color:#5e50b7}.rejected{background:var(--danger-soft);color:#a54b4f}.status-icon{width:52rpx;height:52rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:17rpx;background:rgba(255,255,255,.72);font-weight:850}.status-title,.status-desc{display:block}.status-title{font-size:23rpx;font-weight:780}.status-desc{margin-top:6rpx;font-size:18rpx;line-height:1.5;opacity:.82}
.apply-card{margin-top:18rpx;overflow:hidden;border-radius:30rpx;background:#fff;box-shadow:var(--shadow-card)}.apply-entry{display:flex;align-items:center;gap:18rpx;padding:26rpx}.apply-icon{width:58rpx;height:58rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:19rpx;background:#eef8f3;color:var(--success);font-size:28rpx;font-weight:600}.apply-main{flex:1}.apply-title,.apply-desc{display:block}.apply-title{font-size:24rpx;font-weight:770}.apply-desc{margin-top:6rpx;color:var(--muted);font-size:18rpx;line-height:1.5}
.apply-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20rpx;padding:27rpx 28rpx 10rpx}.close{color:var(--muted);font-size:19rpx}.apply-card input,.apply-card textarea{width:calc(100% - 56rpx);margin:12rpx 28rpx 0;padding:19rpx;border-radius:19rpx;background:#f7f7fa;font-size:21rpx}.apply-card textarea{height:120rpx}.apply-button{margin:18rpx 28rpx 27rpx;height:78rpx;line-height:78rpx;border-radius:23rpx;background:var(--ink);color:#fff;font-size:22rpx;font-weight:760}
.support-note{display:flex;gap:13rpx;align-items:flex-start;margin-top:20rpx;padding:20rpx 22rpx;border-radius:23rpx;background:#efeff3;color:#777781;font-size:18rpx;line-height:1.55}.support-icon{width:34rpx;height:34rpx;flex:none;display:flex;align-items:center;justify-content:center;border-radius:50%;background:#fff;color:#868691;font-weight:800}
</style>
