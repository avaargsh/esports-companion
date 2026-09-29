<script lang="ts">
export default {
  onLaunch() {
    console.info("esports-companion mini program launched")
  }
}
</script>

<style>
page {
  --brand: #6757e6;
  --brand-strong: #5644d6;
  --brand-soft: #efedff;
  --brand-ghost: #f7f5ff;
  --ink: #17171f;
  --ink-2: #4f4f5a;
  --muted: #8e8e99;
  --muted-2: #b4b4bd;
  --bg: #f5f5f8;
  --surface: #ffffff;
  --surface-2: #fafafe;
  --line: #eae9ef;
  --success: #1f9d63;
  --success-soft: #eaf8f1;
  --warning: #b9770e;
  --warning-soft: #fff5df;
  --danger: #d84c51;
  --danger-soft: #fff0f1;
  --radius-sm: 18rpx;
  --radius-md: 24rpx;
  --radius-lg: 32rpx;
  --radius-xl: 40rpx;
  --shadow-card: 0 14rpx 42rpx rgba(30, 26, 55, .055);
  --shadow-float: 0 24rpx 70rpx rgba(30, 26, 55, .11);

  min-height: 100%;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
    "PingFang SC", "Helvetica Neue", sans-serif;
  font-synthesis: none;
}

view,
text,
button,
input,
textarea {
  box-sizing: border-box;
}

button {
  font: inherit;
}

button::after {
  border: 0;
}

.safe-page {
  min-height: 100vh;
  padding: 28rpx 28rpx calc(44rpx + env(safe-area-inset-bottom));
}

.surface-card {
  border: 1rpx solid rgba(20, 20, 30, .035);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.tap-scale {
  transition: transform .12s ease, opacity .12s ease;
}

.tap-scale:active {
  transform: scale(.985);
  opacity: .92;
}

.skeleton {
  overflow: hidden;
  border-radius: 16rpx;
  background:
    linear-gradient(
      90deg,
      #eeeeF3 25%,
      #f7f7fa 37%,
      #eeeeF3 63%
    );
  background-size: 400% 100%;
  animation: shimmer 1.35s ease infinite;
}

@keyframes shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: 0 0; }
}
</style>
