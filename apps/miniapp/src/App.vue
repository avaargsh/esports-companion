<script lang="ts">
export default {}
</script>

<style>
page {
  --brand: #6c5ce7;
  --brand-strong: #5847dc;
  --brand-soft: #f1efff;
  --accent: #13c2c2;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --bg: #f6f6fb;
  --surface: #ffffff;
  --surface-2: #f9f9fc;
  --text: #16161d;
  --text-2: #62626d;
  --muted: #9696a1;
  --line: #ececf2;
  --shadow-card: 0 14rpx 42rpx rgba(27, 22, 60, .07);
  --radius-sm: 18rpx;
  --radius-md: 26rpx;
  --radius-lg: 34rpx;

  min-height: 100%;
  background:
    radial-gradient(circle at 92% 2%, rgba(108, 92, 231, .10), transparent 25%),
    var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
  -webkit-font-smoothing: antialiased;
}

button {
  font: inherit;
}

button::after {
  border: 0;
}

input,
textarea {
  color: var(--text);
}

.safe-page {
  min-height: 100vh;
  padding: 28rpx 28rpx calc(44rpx + env(safe-area-inset-bottom));
}

.surface-card {
  border: 1rpx solid rgba(20, 20, 28, .035);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.pressable {
  transition: transform .16s ease, opacity .16s ease;
}

.pressable:active {
  transform: scale(.985);
  opacity: .9;
}

* {
  box-sizing: border-box;
}
</style>
