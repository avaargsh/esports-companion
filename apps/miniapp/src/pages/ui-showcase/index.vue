<script setup lang="ts">
import EmptyState from "../../components/EmptyState.vue"
import UiBadge from "../../components/ui/UiBadge.vue"
import UiButton from "../../components/ui/UiButton.vue"
import UiCell from "../../components/ui/UiCell.vue"
import { showMessage, showSuccess } from "../../ui/feedback"

function preview(label: string) {
  showMessage(`${label} · Showcase only`)
}
</script>

<template>
  <view class="safe-page showcase">
    <view class="intro">
      <text class="eyebrow">STARTER UI</text>
      <text class="title">Theme & primitives</text>
      <text class="description">
        这里直接渲染脚手架的语义 token 和共享组件。换品牌时优先改 theme.css，不改业务页面。
      </text>
    </view>

    <view class="section">
      <text class="section-title">Theme tokens</text>
      <view class="swatches">
        <view class="swatch"><view class="color brand"></view><text>brand</text></view>
        <view class="swatch"><view class="color success"></view><text>success</text></view>
        <view class="swatch"><view class="color warning"></view><text>warning</text></view>
        <view class="swatch"><view class="color danger"></view><text>danger</text></view>
        <view class="swatch"><view class="color ink"></view><text>ink</text></view>
        <view class="swatch"><view class="color surface"></view><text>surface</text></view>
      </view>
    </view>

    <view class="section">
      <text class="section-title">Buttons</text>
      <view class="stack">
        <UiButton block @click="showSuccess('Primary action')">Primary</UiButton>
        <UiButton block variant="secondary" @click="preview('Secondary')">Secondary</UiButton>
        <UiButton block variant="danger" @click="preview('Danger')">Danger</UiButton>
        <UiButton block disabled>Disabled</UiButton>
        <UiButton block loading>Loading</UiButton>
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
      <view class="cell-card">
        <UiCell title="普通信息" description="非交互行不伪装成按钮" value="Value" />
        <view class="hairline"></view>
        <UiCell
          title="可点击入口"
          description="显式 clickable + arrow"
          clickable
          arrow
          @click="preview('Cell')"
        />
      </view>
    </view>

    <view class="section">
      <text class="section-title">Page states</text>
      <EmptyState
        title="这里还没有内容"
        description="空态也属于产品状态，不应该留下空白页。"
        symbol="·"
        action="示例操作"
        @action="preview('Empty state action')"
      />
    </view>

    <view class="section">
      <text class="section-title">Dark surface</text>
      <view class="dark-card">
        <text class="dark-title">Provider surface</text>
        <text class="dark-description">暗色业务区也从 theme.css 获取颜色。</text>
        <view class="dark-actions">
          <UiButton block>Primary</UiButton>
          <UiButton block variant="secondary" inverse @click="preview('Inverse')">Inverse</UiButton>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.showcase { padding-top: 34rpx; }
.intro { padding: 10rpx 2rpx 18rpx; }
.eyebrow { display:block;color:var(--brand);font-size:16rpx;font-weight:850;letter-spacing:3rpx; }
.title { display:block;margin-top:10rpx;color:var(--ink);font-size:42rpx;font-weight:880; }
.description { display:block;margin-top:12rpx;color:var(--muted);font-size:20rpx;line-height:1.6; }
.section { margin-top:36rpx; }
.section-title { display:block;margin-bottom:16rpx;color:var(--ink);font-size:24rpx;font-weight:800; }
.swatches { display:grid;grid-template-columns:repeat(3,1fr);gap:12rpx; }
.swatch { padding:12rpx;border-radius:var(--radius-md);background:var(--surface);color:var(--muted);font-size:16rpx;box-shadow:var(--shadow-card); }
.color { height:70rpx;margin-bottom:9rpx;border-radius:16rpx; }
.color.brand { background:var(--brand); }.color.success { background:var(--success); }
.color.warning { background:var(--warning); }.color.danger { background:var(--danger); }
.color.ink { background:var(--ink); }.color.surface { border:1rpx solid var(--line);background:var(--surface); }
.stack { display:flex;flex-direction:column;gap:12rpx; }
.badge-row { display:flex;flex-wrap:wrap;gap:10rpx; }
.cell-card { overflow:hidden;border-radius:var(--radius-lg);box-shadow:var(--shadow-card); }
.hairline { height:1rpx;margin-left:24rpx;background:var(--line); }
.dark-card { padding:28rpx;border-radius:var(--radius-lg);background:var(--provider-surface);color:#fff; }
.dark-title { display:block;font-size:27rpx;font-weight:800; }
.dark-description { display:block;margin-top:8rpx;color:var(--provider-muted);font-size:19rpx; }
.dark-actions { display:flex;flex-direction:column;gap:12rpx;margin-top:24rpx; }
</style>
