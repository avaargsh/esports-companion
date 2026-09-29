<script setup lang="ts">
function openPool() {
  uni.navigateTo({ url: "/pages-player/order-pool/index" })
}
</script>

<template>
  <view class="page">
    <view class="summary">
      <view class="topline">
        <view>
          <text class="label">今日收益</text>
          <view class="amount">¥ 0.00</view>
        </view>
        <view class="status">● 接单中</view>
      </view>
      <view class="stats">
        <view><text class="num">0</text><text class="name">今日订单</text></view>
        <view><text class="num">0</text><text class="name">待服务</text></view>
        <view><text class="num">--</text><text class="name">好评率</text></view>
      </view>
      <button class="primary" @click="openPool">去抢单</button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.summary { padding: 36rpx; border-radius: 36rpx; background: #17171f; color: white; }
.topline { display: flex; justify-content: space-between; align-items: flex-start; }
.label { color: #aaaab4; font-size: 22rpx; }
.amount { margin-top: 12rpx; font-size: 54rpx; font-weight: 800; }
.status { padding: 12rpx 18rpx; border-radius: 999rpx; background: rgba(34,197,94,.14); color: #5ddb8b; font-size: 22rpx; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 44rpx; padding-top: 30rpx; border-top: 1rpx solid rgba(255,255,255,.08); }
.stats view { text-align: center; }
.num { display: block; font-size: 32rpx; font-weight: 700; }
.name { display: block; margin-top: 8rpx; color: #aaaab4; font-size: 20rpx; }
.primary { margin-top: 34rpx; height: 88rpx; line-height: 88rpx; border-radius: 28rpx; background: #6c5ce7; color: white; font-size: 28rpx; font-weight: 700; }
</style>
