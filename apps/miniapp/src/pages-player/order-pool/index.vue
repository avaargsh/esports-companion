<template>
  <view class="page">
    <view class="filter">
      <text class="active">全部</text>
      <text>王者荣耀</text>
      <text>英雄联盟</text>
    </view>

    <view class="order-card">
      <view class="head">
        <view>
          <view class="game">王者荣耀 · 娱乐陪玩</view>
          <view class="meta">60分钟 · 2分钟前发布</view>
        </view>
        <view class="income">¥24</view>
      </view>
      <view class="tags">
        <text>钻石局</text>
        <text>娱乐上分</text>
      </view>
      <button class="claim">立即抢单</button>
    </view>

    <view class="tip">接下来接入 /api/v1/player/order-pool 与 CAS claim。</view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.filter { display: flex; gap: 34rpx; padding: 10rpx 4rpx 28rpx; color: #92929d; font-size: 24rpx; }
.filter .active { color: #15151b; font-weight: 700; }
.order-card { padding: 30rpx; border-radius: 32rpx; background: white; box-shadow: 0 12rpx 40rpx rgba(25,20,60,.06); }
.head { display: flex; justify-content: space-between; gap: 20rpx; }
.game { font-size: 30rpx; font-weight: 700; }
.meta { margin-top: 10rpx; color: #92929d; font-size: 22rpx; }
.income { color: #6c5ce7; font-size: 38rpx; font-weight: 800; }
.tags { display: flex; gap: 12rpx; margin-top: 26rpx; }
.tags text { padding: 8rpx 14rpx; border-radius: 999rpx; background: #f5f3ff; color: #6c5ce7; font-size: 20rpx; }
.claim { margin-top: 28rpx; height: 82rpx; line-height: 82rpx; border-radius: 26rpx; background: #6c5ce7; color: white; font-size: 26rpx; font-weight: 700; }
.tip { margin-top: 24rpx; color: #92929d; font-size: 22rpx; line-height: 1.6; }
</style>
