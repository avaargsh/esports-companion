<script setup lang="ts">
import { onMounted, ref } from "vue"
import { request } from "../../api/client"

type Game = {
  id: string
  code: string
  name: string
  icon_url?: string
}

const games = ref<Game[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    games.value = await request<Game[]>("/games")
  } finally {
    loading.value = false
  }
})

function openPlayerWorkspace() {
  uni.navigateTo({ url: "/pages-player/workbench/index" })
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <view>
        <text class="eyebrow">ESPORTS COMPANION</text>
        <view class="title">今晚一起上分</view>
        <view class="subtitle">在线大神 · 随叫随到</view>
      </view>
      <button class="workspace-button" @click="openPlayerWorkspace">陪玩工作台</button>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">热门游戏</text>
        <text class="section-link">全部</text>
      </view>

      <view v-if="loading" class="empty-card">加载中...</view>
      <view v-else class="game-grid">
        <view v-for="game in games" :key="game.id" class="game-card">
          <view class="game-icon">{{ game.name.slice(0, 1) }}</view>
          <text class="game-name">{{ game.name }}</text>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">推荐大神</text>
        <text class="section-link">查看更多</text>
      </view>

      <view class="provider-card">
        <view class="avatar">鹿</view>
        <view class="provider-main">
          <view class="provider-title">
            <text class="provider-name">小鹿</text>
            <text class="online">接单中</text>
          </view>
          <text class="provider-desc">王者荣耀 · 国服辅助 · 娱乐陪玩</text>
          <view class="provider-meta">
            <text>★ 4.9</text>
            <text>268单</text>
          </view>
        </view>
        <view class="price">
          <text class="price-value">¥30</text>
          <text class="price-unit">/小时</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 28rpx; }
.hero {
  min-height: 300rpx;
  padding: 42rpx;
  border-radius: 36rpx;
  background: linear-gradient(135deg, #6c5ce7, #8b7cf6);
  color: white;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.eyebrow { font-size: 20rpx; opacity: .72; letter-spacing: 3rpx; }
.title { margin-top: 18rpx; font-size: 48rpx; font-weight: 800; }
.subtitle { margin-top: 12rpx; font-size: 26rpx; opacity: .88; }
.workspace-button {
  margin: 34rpx 0 0;
  width: 220rpx;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 24rpx;
  background: rgba(255,255,255,.18);
  color: white;
  font-size: 24rpx;
}
.section { margin-top: 40rpx; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 22rpx; }
.section-title { font-size: 32rpx; font-weight: 700; }
.section-link { color: #92929d; font-size: 24rpx; }
.game-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18rpx; }
.game-card { padding: 24rpx 10rpx; border-radius: 28rpx; background: white; text-align: center; }
.game-icon {
  width: 76rpx; height: 76rpx; margin: 0 auto 14rpx; border-radius: 24rpx;
  display: flex; align-items: center; justify-content: center;
  background: #f0edff; color: #6c5ce7; font-size: 30rpx; font-weight: 800;
}
.game-name { font-size: 22rpx; }
.provider-card {
  display: flex; align-items: center; gap: 22rpx;
  padding: 28rpx; border-radius: 32rpx; background: white;
  box-shadow: 0 12rpx 40rpx rgba(25, 20, 60, .06);
}
.avatar {
  width: 104rpx; height: 104rpx; border-radius: 32rpx;
  background: #efeaff; color: #6c5ce7;
  display: flex; align-items: center; justify-content: center;
  font-size: 40rpx; font-weight: 800;
}
.provider-main { flex: 1; min-width: 0; }
.provider-title { display: flex; align-items: center; gap: 12rpx; }
.provider-name { font-size: 30rpx; font-weight: 700; }
.online { padding: 6rpx 12rpx; border-radius: 999rpx; background: #eafbf2; color: #22a665; font-size: 18rpx; }
.provider-desc { display: block; margin-top: 10rpx; color: #686872; font-size: 22rpx; }
.provider-meta { display: flex; gap: 18rpx; margin-top: 14rpx; color: #92929d; font-size: 20rpx; }
.price { text-align: right; }
.price-value { display: block; color: #6c5ce7; font-size: 34rpx; font-weight: 800; }
.price-unit { color: #92929d; font-size: 18rpx; }
.empty-card { padding: 40rpx; border-radius: 28rpx; background: white; color: #92929d; text-align: center; }
</style>
