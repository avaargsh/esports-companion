<script setup lang="ts">
import { computed, ref } from "vue"
import { onShow } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import EmptyState from "../../components/EmptyState.vue"
import OrderCard from "../../components/OrderCard.vue"
import type { Order } from "../../types/domain"
import { isActiveOrder } from "../../utils/order"
import { showMessage } from "../../ui/feedback"

type Filter="all"|"active"|"done"
const orders=ref<Order[]>([])
const loading=ref(false)
const filter=ref<Filter>("all")
const activeCount=computed(()=>orders.value.filter(i=>isActiveOrder(i.status)).length)
const doneCount=computed(()=>orders.value.length-activeCount.value)
const visibleOrders=computed(()=>{
  if(filter.value==="active")return orders.value.filter(i=>isActiveOrder(i.status))
  if(filter.value==="done")return orders.value.filter(i=>!isActiveOrder(i.status))
  return orders.value
})
async function load(){
  loading.value=true
  try{
    const identities=await getDemoIdentities()
    orders.value=await request<Order[]>("/orders?limit=50",{userId:identities.customer.userId})
  }catch(error){
    showMessage(error instanceof Error?error.message:"订单加载失败")
  }finally{loading.value=false}
}
onShow(()=>{void load()})
function openOrder(order:Order){uni.navigateTo({url:`/pages/order-detail/index?id=${order.id}`})}
function goHome(){uni.switchTab({url:"/pages/home/index"})}
</script>

<template>
  <view class="safe-page custom-safe-page orders-page">
    <view class="heading">
      <text class="title">我的订单</text>
      <text class="subtitle">服务状态、售后与评价都在订单里处理。</text>
    </view>
    <view class="tabs">
      <text :class="{active:filter==='all'}" @click="filter='all'">全部 {{ orders.length }}</text>
      <text :class="{active:filter==='active'}" @click="filter='active'">进行中 {{ activeCount }}</text>
      <text :class="{active:filter==='done'}" @click="filter='done'">已结束 {{ doneCount }}</text>
    </view>

    <view v-if="loading" class="list">
      <view v-for="n in 4" :key="n" class="skeleton order-skeleton"></view>
    </view>
    <EmptyState
      v-else-if="visibleOrders.length===0"
      :title="orders.length ? '这个分类暂无订单' : '还没有订单'"
      :description="orders.length ? '切换分类查看其它订单' : '从首页选游戏，即可创建第一笔陪玩订单'"
      :action="orders.length ? '' : '去下单'"
      symbol="单"
      @action="goHome"
    />
    <view v-else class="list">
      <OrderCard v-for="item in visibleOrders" :key="item.id" :order="item" @open="openOrder" />
    </view>
  </view>
</template>

<style scoped>
.heading { padding:10rpx 3rpx 26rpx; }
.title { display:block;font-size:39rpx;font-weight:850;letter-spacing:-1rpx; }
.subtitle { display:block;margin-top:8rpx;color:var(--muted);font-size:20rpx; }
.tabs {
  display:inline-flex;gap:4rpx;margin-bottom:22rpx;padding:5rpx;border-radius:19rpx;background:#ececf1;
}
.tabs text { min-width:118rpx;padding:12rpx 16rpx;border-radius:15rpx;color:#7d7d87;text-align:center;font-size:19rpx; }
.tabs .active { background:#fff;color:var(--ink);font-weight:750;box-shadow:0 4rpx 14rpx rgba(20,20,30,.05); }
.list { display:flex;flex-direction:column;gap:13rpx; }
.order-skeleton { height:190rpx;border-radius:30rpx; }
</style>
