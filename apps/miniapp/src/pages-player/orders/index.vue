<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order } from "../../types/domain"
import { isActiveOrder, orderStatusMeta } from "../../utils/order"
import { showMessage } from "../../ui/feedback"

const orders=ref<Order[]>([])
const loading=ref(false)
const filter=ref<"ACTIVE"|"DONE">("ACTIVE")
const activeCount=computed(()=>orders.value.filter(item=>isActiveOrder(item.status)).length)
const doneCount=computed(()=>orders.value.length-activeCount.value)
const visibleOrders=computed(()=>orders.value.filter(item=>filter.value==="ACTIVE"?isActiveOrder(item.status):!isActiveOrder(item.status)))
async function load(){
  loading.value=true
  try{
    const identities=await getDemoIdentities()
    const userId=identities.players[0]?.userId
    if(!userId)return
    orders.value=await request<Order[]>("/player/orders",{userId})
  }catch(error){
    showMessage(error instanceof Error?error.message:"服务订单加载失败")
  }finally{
    loading.value=false
  }
}
function openOrder(id:string){uni.navigateTo({url:`/pages-player/order-detail/index?id=${id}`})}
onShow(()=>{void load()})
</script>
<template>
  <view class="page">
    <view class="heading">
      <text class="eyebrow">服务管理</text>
      <text class="title">服务订单</text>
    </view>
    <view class="tabs">
      <text :class="{active:filter==='ACTIVE'}" @click="filter='ACTIVE'">待履约 {{ activeCount }}</text>
      <text :class="{active:filter==='DONE'}" @click="filter='DONE'">已结束 {{ doneCount }}</text>
    </view>
    <view v-if="loading" class="list">
      <view v-for="n in 3" :key="n" class="order-skeleton"></view>
    </view>
    <view v-else-if="!visibleOrders.length" class="empty">
      <view class="empty-icon">单</view>
      <text>{{ filter==="ACTIVE" ? "暂无待履约服务" : "暂无已结束服务" }}</text>
    </view>
    <view class="list">
      <view v-for="item in visibleOrders" :key="item.id" class="card" @click="openOrder(item.id)">
        <view class="card-top">
          <text class="number">{{ item.order_no }}</text>
          <text class="chevron">›</text>
        </view>
        <view class="card-main">
          <view>
            <text class="status">{{ orderStatusMeta(item.status,"PLAYER").label }}</text>
            <text class="status-desc">{{ orderStatusMeta(item.status,"PLAYER").description }}</text>
          </view>
          <view class="income"><text>本单收入</text><b><small>¥</small>{{ (item.player_amount/100).toFixed(2) }}</b></view>
        </view>
      </view>
    </view>
  </view>
</template>
<style scoped>
.page{min-height:100vh;padding:28rpx;background:#101016;color:#fff}.heading{padding:9rpx 2rpx 20rpx}.eyebrow,.title{display:block}.eyebrow{color:#6f6d79;font-size:15rpx;font-weight:800;letter-spacing:2.5rpx}.title{margin-top:7rpx;font-size:36rpx;font-weight:850}.tabs{display:inline-flex;gap:4rpx;margin-bottom:18rpx;padding:5rpx;border-radius:18rpx;background:#191920}.tabs text{min-width:130rpx;padding:11rpx 16rpx;border-radius:14rpx;color:#777582;text-align:center;font-size:18rpx}.tabs .active{background:#2a2738;color:#fff;font-weight:750}
.list{display:flex;flex-direction:column;gap:12rpx}.order-skeleton{height:180rpx;border-radius:29rpx;background:#191920}.card{padding:24rpx;border:1rpx solid rgba(255,255,255,.05);border-radius:29rpx;background:#191920}.card-top{display:flex;justify-content:space-between;gap:15rpx}.number{color:#696773;font-size:15rpx}.chevron{color:#575561;font-size:27rpx}.card-main{display:flex;align-items:flex-end;justify-content:space-between;gap:20rpx;margin-top:17rpx}.status,.status-desc{display:block}.status{font-size:25rpx;font-weight:790}.status-desc{margin-top:6rpx;color:#777582;font-size:16rpx}.income{text-align:right}.income>text{display:block;color:#777582;font-size:15rpx}.income b{display:block;margin-top:3rpx;color:#afa3fb;font-size:29rpx}.income small{font-size:16rpx}.empty{padding:100rpx 20rpx;color:#777582;text-align:center;font-size:19rpx}.empty-icon{width:88rpx;height:88rpx;margin:0 auto 18rpx;display:flex;align-items:center;justify-content:center;border-radius:28rpx;background:#191920;color:#7f72d9;font-size:28rpx;font-weight:800}
</style>
