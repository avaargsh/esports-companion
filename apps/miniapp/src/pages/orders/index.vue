<template>
  <view class="page">
    <view class="empty">
      <view class="icon">单</view>
      <view class="title">订单中心</view>
      <view class="desc">这里将承载 WAITING_PAYMENT → SETTLED 的完整状态展示。</view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.empty { margin-top: 120rpx; text-align: center; color: #92929d; }
.icon {
  width: 120rpx; height: 120rpx; margin: auto; border-radius: 36rpx;
  background: #efeaff; color: #6c5ce7; display: flex; align-items: center; justify-content: center;
  font-size: 42rpx; font-weight: 800;
}
.title { margin-top: 30rpx; color: #15151b; font-size: 34rpx; font-weight: 700; }
.desc { margin-top: 14rpx; font-size: 24rpx; line-height: 1.6; }
</style>
