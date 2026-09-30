<script setup lang="ts">
import { computed, ref } from "vue"
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import { isWeChatAuthMode } from "../../api/config"
import type { Game, Order } from "../../types/domain"
import SampleJourney from "../../components/SampleJourney.vue"
import { claimErrorMessage } from "../../utils/order"
import { showSuccess, showMessage } from "../../ui/feedback"

type Player={id:string;user_id:string;display_name:string;verification_status:string;service_status:string}
const games=ref<Game[]>([])
const gameId=ref("")
const orders=ref<Order[]>([])
const profile=ref<Player|null>(null)
const playerUserId=ref("")
const loading=ref(false)
const claimingId=ref("")
const demoMode=!isWeChatAuthMode()
const bestIncome=computed(()=>orders.value.reduce((max,i)=>Math.max(max,i.player_amount),0))
const canClaim=computed(()=>profile.value?.verification_status==="APPROVED"&&profile.value?.service_status==="AVAILABLE")
const claimBlockReason=computed(()=>{
  if(!profile.value)return "正在同步陪玩身份"
  if(profile.value.verification_status!=="APPROVED")return "认证未通过，暂不可接单"
  if(profile.value.service_status!=="AVAILABLE")return "已暂停接单，请先回工作台开启接单"
  return ""
})
async function loadPool(){
  if(!gameId.value||!playerUserId.value)return
  loading.value=true
  try{
    orders.value=await request<Order[]>(`/player/order-pool?game_id=${gameId.value}`,{userId:playerUserId.value})
  }catch(error){
    orders.value=[]
    showMessage(claimErrorMessage(error instanceof Error?error.message:""))
  }finally{loading.value=false}
}
async function bootstrap(){
  try{
    const identities=await getDemoIdentities()
    playerUserId.value=identities.players[0]?.userId??""
    if(!playerUserId.value)throw new Error("PLAYER_PROFILE_NOT_FOUND")
    const [p,g]=await Promise.all([
      request<Player>("/player/profile",{userId:playerUserId.value}),
      request<Game[]>("/games")
    ])
    profile.value=p;games.value=g
    if(!gameId.value&&games.value.length)gameId.value=games.value[0].id
    await loadPool()
  }catch(error){showMessage(claimErrorMessage(error instanceof Error?error.message:""))}
}
async function selectGame(id:string){if(gameId.value===id)return;gameId.value=id;await loadPool()}
function backToWorkbench(){uni.navigateBack()}
async function claim(order:Order){
  if(!playerUserId.value||claimingId.value)return
  if(!canClaim.value){showMessage(claimBlockReason.value);return}
  claimingId.value=order.id
  try{
    const claimed=await request<Order>(`/player/orders/${order.id}/claim`,{
      method:"POST",userId:playerUserId.value,data:{expected_version:order.version}
    })
    showSuccess("接单成功")
    uni.navigateTo({url:`/pages-player/order-detail/index?id=${claimed.id}`})
  }catch(error){
    showMessage(claimErrorMessage(error instanceof Error?error.message:""))
    await loadPool()
  }finally{claimingId.value=""}
}
onShow(()=>{void bootstrap()})
onPullDownRefresh(async()=>{await loadPool();uni.stopPullDownRefresh()})
</script>

<template>
  <view class="page">
    <view class="heading">
      <view>
        <text class="eyebrow">接单市场</text>
        <text class="title">抢单大厅</text>
      </view>
      <view class="live"><text class="pulse"></text>{{ canClaim ? "可接单" : "暂停" }}</view>
    </view>

    <SampleJourney
      v-if="demoMode"
      :step="3"
      role="陪玩端"
      title="找到刚才支付的订单"
      description="只展示与你已启用服务匹配的公开订单。点击「立即抢单」进入履约。"
      dark
    />

    <view v-if="claimBlockReason" class="guard">
      <text>{{ claimBlockReason }}</text>
      <text class="guard-link" @click="backToWorkbench">去工作台 ›</text>
    </view>

    <view class="overview">
      <view><b>{{ orders.length }}</b><text>可抢订单</text></view>
      <view><b>¥{{ (bestIncome/100).toFixed(0) }}</b><text>最高单笔收入</text></view>
    </view>

    <scroll-view scroll-x class="filter" :show-scrollbar="false">
      <view class="filter-row">
        <text v-for="game in games" :key="game.id" :class="{active:gameId===game.id}" @click="selectGame(game.id)">
          {{ game.name }}
        </text>
      </view>
    </scroll-view>

    <view v-if="loading" class="list">
      <view v-for="n in 3" :key="n" class="order-skeleton"></view>
    </view>

    <view v-else-if="!orders.length" class="empty">
      <view class="empty-icon">⌁</view>
      <text class="empty-title">现在没有可接订单</text>
      <text class="empty-desc">只展示与你已启用服务匹配的订单，下拉即可刷新。</text>
      <button class="ghost" @click="loadPool">刷新订单</button>
    </view>

    <view v-else class="list">
      <view v-for="order in orders" :key="order.id" class="order-card">
        <view class="order-top">
          <view class="trust"><text class="trust-dot"></text>平台担保</view>
          <text class="order-no">{{ order.order_no }}</text>
        </view>
        <view class="order-main">
          <view>
            <text class="order-title">待接服务</text>
            <text class="order-meta">数量 × {{ order.quantity || 1 }}</text>
          </view>
          <view class="income">
            <text>预计收入</text>
            <b><small>¥</small>{{ (order.player_amount/100).toFixed(2) }}</b>
          </view>
        </view>
        <view class="amount-row">
          <text>服务数量 × {{ order.quantity || 1 }}</text>
          <text>订单总额 ¥{{ (order.total_amount/100).toFixed(2) }}</text>
        </view>
        <button class="claim" :disabled="!canClaim||!!claimingId" @click="claim(order)">
          {{ claimingId===order.id ? "正在抢单…" : canClaim ? "立即抢单" : "暂不可接单" }}
        </button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page{min-height:100vh;padding:28rpx;padding-bottom:calc(42rpx + env(safe-area-inset-bottom));background:var(--inverse-bg);color:#fff}
.heading{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;padding:9rpx 2rpx 23rpx}.eyebrow,.title{display:block}.eyebrow{color:#6f6d79;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;font-size:36rpx;font-weight:850}.live{display:flex;align-items:center;gap:8rpx;padding:9rpx 13rpx;border-radius:999rpx;background:rgba(44,190,118,.1);color:#5ed894;font-size:17rpx;font-weight:700}.pulse{width:10rpx;height:10rpx;border-radius:50%;background:currentColor}
.guard{display:flex;justify-content:space-between;gap:14rpx;margin-bottom:14rpx;padding:16rpx 18rpx;border-radius:19rpx;background:rgba(215,157,55,.1);color:#d8ab5d;font-size:17rpx}.guard-link{flex:none;color:#aa9df8;font-weight:700}
.overview{display:grid;grid-template-columns:1fr 1fr;gap:10rpx;margin-bottom:18rpx}.overview view{padding:20rpx 22rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:23rpx;background:var(--inverse-surface)}.overview b,.overview text{display:block}.overview b{font-size:27rpx}.overview text{margin-top:5rpx;color:#777582;font-size:16rpx}
.filter{width:100%;margin-bottom:18rpx}.filter-row{display:flex;gap:8rpx;white-space:nowrap}.filter-row text{flex:none;padding:12rpx 18rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:17rpx;background:var(--inverse-surface);color:#85838e;font-size:18rpx}.filter-row text.active{border-color:var(--brand);background:var(--brand);color:#fff;font-weight:750}
.list{display:flex;flex-direction:column;gap:13rpx}.order-skeleton{height:250rpx;border-radius:30rpx;background:var(--inverse-surface)}
.order-card{padding:25rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:30rpx;background:var(--inverse-surface)}.order-top{display:flex;align-items:center;justify-content:space-between;gap:15rpx}.trust{display:flex;align-items:center;gap:7rpx;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(44,190,118,.08);color:#58ca8c;font-size:15rpx;font-weight:700}.trust-dot{width:8rpx;height:8rpx;border-radius:50%;background:currentColor}.order-no{max-width:330rpx;overflow:hidden;color:#676572;font-size:15rpx;text-overflow:ellipsis;white-space:nowrap}
.order-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:22rpx}.order-title,.order-meta{display:block}.order-title{font-size:26rpx;font-weight:790}.order-meta{margin-top:6rpx;color:#777582;font-size:17rpx}.income{text-align:right}.income>text{display:block;color:#777582;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#b0a4fb;font-size:31rpx}.income small{font-size:17rpx}
.amount-row{display:flex;justify-content:space-between;gap:16rpx;margin-top:21rpx;padding-top:17rpx;border-top:1rpx solid rgba(255,255,255,.05);color:#706e79;font-size:16rpx}
.claim{margin-top:18rpx;height:76rpx;line-height:76rpx;border-radius:22rpx;background:var(--brand);color:#fff;font-size:22rpx;font-weight:770}.claim[disabled]{background:#292832;color:#666471;opacity:1}
.empty{padding:80rpx 24rpx;text-align:center}.empty-icon{width:94rpx;height:94rpx;margin:auto;display:flex;align-items:center;justify-content:center;border-radius:30rpx;background:#1b1b23;color:#8576ec;font-size:37rpx}.empty-title,.empty-desc{display:block}.empty-title{margin-top:21rpx;font-size:26rpx;font-weight:780}.empty-desc{margin:9rpx auto 0;max-width:500rpx;color:#73717d;font-size:18rpx;line-height:1.55}.ghost{width:210rpx;height:68rpx;margin:23rpx auto 0;line-height:68rpx;border-radius:20rpx;background:var(--inverse-control-strong);color:#c2bfca;font-size:19rpx}
</style>
