<script setup lang="ts">
import UiBadge from "../../components/ui/UiBadge.vue"
import UiButton from "../../components/ui/UiButton.vue"
import UiCell from "../../components/ui/UiCell.vue"
import { confirmAction, showMessage, showSuccess } from "../../ui/feedback"

async function demoConfirm() {
  const confirmed = await confirmAction({
    title: "确认示例操作？",
    content: "Showcase 只演示交互，不会修改任何业务数据。",
    confirmText: "确认"
  })
  showMessage(confirmed ? "已确认" : "已取消")
}
</script>

<template>
  <view class="safe-page showcase">
    <view class="intro surface-card">
      <text class="eyebrow">STARTER UI LAB</text>
      <text class="title">Mini Program UI Showcase</text>
      <text class="description">
        这是开发者参考页，不属于产品导航。用于验证主题 Token、基础组件和微信交互反馈。
      </text>
    </view>

    <view class="section">
      <text class="section-title">Theme tokens</text>
      <view class="swatches">
        <view class="swatch brand"><text>Brand</text></view>
        <view class="swatch success"><text>Success</text></view>
        <view class="swatch warning"><text>Warning</text></view>
        <view class="swatch danger"><text>Danger</text></view>
      </view>
    </view>

    <view class="section">
      <text class="section-title">Buttons</text>
      <view class="stack">
        <UiButton block @click="showSuccess('Primary action')">Primary</UiButton>
        <UiButton block variant="secondary" @click="showMessage('Secondary action')">
          Secondary
        </UiButton>
        <UiButton block variant="danger" @click="demoConfirm">Danger / Confirm</UiButton>
        <UiButton variant="plain" size="sm" @click="showMessage('Plain action')">
          Plain action
        </UiButton>
      </view>
    </view>

    <view class="section">
      <text class="section-title">Badges</text>
      <view class="badge-row">
        <UiBadge tone="neutral">Neutral</UiBadge>
        <UiBadge tone="brand" dot>Brand</UiBadge>
        <UiBadge tone="success" dot>Success</UiBadge>
        <UiBadge tone="warning" dot>Warning</UiBadge>
        <UiBadge tone="danger" dot>Danger</UiBadge>
      </view>
    </view>

    <view class="section">
      <text class="section-title">Cells</text>
      <view class="cell-group surface-card">
        <UiCell
          title="普通入口"
          description="明确声明 clickable 才具有点击语义"
          clickable
          arrow
          @click="showMessage('Cell clicked')"
        />
        <view class="divider"></view>
        <UiCell title="只读信息" value="Value" />
      </view>
    </view>

    <view class="section">
      <text class="section-title">Inverse surface</text>
      <view class="inverse-card">
        <text class="inverse-title">Provider / dark workspace</text>
        <text class="inverse-description">
          反色界面仍使用同一套语义 Token，不另起一套业务颜色。
        </text>
        <view class="inverse-actions">
          <UiButton block inverse @click="showSuccess('Inverse primary')">
            Primary
          </UiButton>
          <UiButton block inverse variant="secondary" @click="showMessage('Inverse secondary')">
            Secondary
          </UiButton>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.showcase {
  padding-top: 28rpx;
}

.intro {
  padding: 32rpx;
}

.eyebrow,
.title,
.description,
.section-title,
.inverse-title,
.inverse-description {
  display: block;
}

.eyebrow {
  color: var(--brand);
  font-size: 16rpx;
  font-weight: 800;
  letter-spacing: 2rpx;
}

.title {
  margin-top: 10rpx;
  color: var(--ink);
  font-size: 36rpx;
  font-weight: 850;
}

.description {
  margin-top: 12rpx;
  color: var(--muted);
  font-size: 20rpx;
  line-height: 1.6;
}

.section {
  margin-top: 34rpx;
}

.section-title {
  margin-bottom: 16rpx;
  color: var(--ink);
  font-size: 25rpx;
  font-weight: 800;
}

.swatches {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
}

.swatch {
  min-height: 110rpx;
  padding: 18rpx;
  display: flex;
  align-items: flex-end;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: 18rpx;
  font-weight: 750;
}

.swatch.brand { background: var(--brand); }
.swatch.success { background: var(--success); }
.swatch.warning { background: var(--warning); }
.swatch.danger { background: var(--danger); }

.stack {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}

.cell-group {
  overflow: hidden;
}

.divider {
  height: 1rpx;
  margin-left: 24rpx;
  background: var(--line);
}

.inverse-card {
  padding: 28rpx;
  border-radius: var(--radius-lg);
  background: var(--inverse-surface);
  color: #fff;
}

.inverse-title {
  font-size: 26rpx;
  font-weight: 800;
}

.inverse-description {
  margin-top: 8rpx;
  color: var(--inverse-muted);
  font-size: 18rpx;
  line-height: 1.55;
}

.inverse-actions {
  display: grid;
  gap: 12rpx;
  margin-top: 24rpx;
}
</style>
