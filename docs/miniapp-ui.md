# Mini Program UI Foundation

The Mini Program ships a small built-in UI foundation for **WeChat-native interaction quality without coupling the Vue/uni-app application to a second component runtime**.

Reference direction:

- WeChat official WeUI Mini Program: https://github.com/wechat-miniprogram/weui-miniprogram
- WeUI WXSS: https://github.com/Tencent/weui-wxss
- WeChat Mini Program examples: https://github.com/wechat-miniprogram/miniprogram-demo

The goal is not to clone every WeUI component. The starter keeps a small semantic layer that survives product re-skinning and keeps page code consistent.

## Principles

1. **Native controls first**
   - Prefer Mini Program `button`, `input`, `textarea`, picker and system feedback APIs.
   - Wrap them only when the wrapper adds a stable product contract: size, state, feedback or accessibility.

2. **One primary action per decision**
   - Primary buttons are reserved for the page's dominant next action.
   - Secondary, plain and destructive actions remain visually distinct.

3. **Touch targets are not decorative**
   - Interactive controls use at least `88rpx` as the default tap-height baseline.
   - Small visual labels may be smaller, but interactive labels should still sit inside a sufficient hit area.

4. **Safe area is part of layout**
   - All full pages account for the bottom safe area.
   - Custom-navigation pages use `--status-bar-height` when supplied by uni-app, with the platform safe-area inset as fallback.

5. **Loading / empty / error / content are first-class states**
   - Do not leave a blank page while requests are running.
   - Errors need a retry path when retry is meaningful.
   - Empty states explain what happened and what the user can do next.

6. **System feedback for short-lived state**
   - Use toast for success and recoverable errors.
   - Use modal confirmation only for consequential or destructive actions.
   - Use masked loading only for short blocking operations; avoid leaving it visible around long-running background work.

7. **Business state stays out of the UI kit**
   - Components render state and emit intent.
   - Order/payment/withdrawal state machines remain in domain/API layers.

## Theme vs foundation

The starter deliberately separates **brand/theme choices** from **structural UI contracts**:

- `apps/miniapp/src/styles/theme.css` — replaceable product palette, semantic colors, light/dark product surfaces and elevation.
- `apps/miniapp/src/styles/foundation.css` — spacing, radii, control heights, safe-area/layout helpers, motion and shared structural behavior.

For a fork/rebrand, start with `theme.css`. Do not edit business pages merely to replace the primary color.

Theme variables include:

- `--brand`, `--brand-soft`
- `--ink`, `--muted`
- `--bg`, `--surface`, `--line`
- `--success`, `--warning`, `--danger`
- `--radius-*`
- `--shadow-card`, `--shadow-float`

Foundation/layout contracts:

- `--tap-min: 88rpx`
- `--control-height: 88rpx`
- `--control-height-sm: 72rpx`
- `--space-1 ... --space-6`

Pages should prefer semantic tokens over introducing new one-off colors. Product-specific surfaces such as the home hero or provider workspace should also consume named theme variables rather than repeating palette literals.

## UI Showcase

A real Mini Program showcase page lives at:

`/pages/ui-showcase/index`

It renders the current theme tokens and shared primitives directly:

- buttons and interaction states;
- semantic badges;
- static vs clickable cells;
- empty-state treatment;
- provider/dark surface behavior.

Use it as the first visual smoke test after changing `theme.css`. It is intentionally not a tab-bar destination or production workflow; it exists as a starter/development reference surface.

## Built-in primitives

### UiButton

`src/components/ui/UiButton.vue`

Variants:

- `primary`
- `secondary`
- `danger`
- `plain`

States:

- loading
- disabled
- pressed feedback
- block / compact sizing
- inverse surface for dark containers

Example:

```vue
<script setup lang="ts">
import UiButton from "@/components/ui/UiButton.vue"
</script>

<template>
  <UiButton :loading="saving" block @click="save">
    保存
  </UiButton>
</template>
```

The uni-app Mini Program compiler does not support arbitrary attribute spreading on this wrapper. Use `UiButton` for ordinary product actions. When a button requires a WeChat capability contract such as `open-type` plus capability-specific events, use the native `button` directly (or add an explicit typed prop/event to `UiButton`) rather than relying on implicit passthrough.

### UiCell

`src/components/ui/UiCell.vue`

Use it for settings, account, order entry points and compact key/value rows.

```vue
<UiCell
  title="我的订单"
  description="进行中的服务、历史订单与售后"
  clickable
  arrow
  @click="openOrders"
/>
```

A cell is only tappable when `clickable` is explicit. This avoids visual rows accidentally behaving like hidden buttons.

### UiBadge

`src/components/ui/UiBadge.vue`

Use `dot` for compact state indicators. Order `StatusTag` is built on this primitive so customer/provider status surfaces share the same visual semantics.

Tones:

- neutral
- brand
- success
- warning
- danger

Badges are for compact status or metadata. They are not buttons.

### PrimaryActionBar

`src/components/PrimaryActionBar.vue`

Fixed bottom actions are built on `UiButton` and include bottom safe-area handling. Use this shared bar for the dominant page mutation instead of hand-building another fixed CTA layer.

## Interaction contract

Mini Program page files must not call `uni.showToast`, `uni.showModal`, `uni.showLoading` or `uni.hideLoading` directly.

All transient feedback goes through `src/ui/feedback.ts`. This keeps wording, duration, confirmation behavior and future analytics/accessibility changes in one place. CI enforces this rule with:

```bash
cd apps/miniapp
npm run ui-check
```

Consequential state changes require an explicit confirmation before the mutation starts. Current guarded examples include customer order completion/cancellation/refund/dispute flows and provider withdrawal submission.

## Feedback helpers

`src/ui/feedback.ts`

Available helpers:

```ts
showSuccess("已保存")
showError(error, "保存失败")

const confirmed = await confirmAction({
  title: "确认取消订单？",
  content: "取消后无法恢复"
})

await withLoading("提交中", () => submit())
```

### Feedback rules

- **Success toast:** completed action with no further decision.
- **Error toast:** short recoverable error; page-level failures still need an inline state and retry entry.
- **Confirm modal:** destructive / irreversible / money-affecting action.
- **Loading mask:** short blocking mutation only.

Do not stack modal + loading + toast for the same non-destructive action unless each state is genuinely required.

## Page-state pattern

Recommended page structure:

```text
request starts
  -> skeleton / local loading
  -> success -> content
  -> empty   -> EmptyState + optional action
  -> failure -> EmptyState + retry
```

For list refreshes, keep existing content visible when possible and show a lightweight refresh indicator instead of replacing the entire page with a blocking spinner.

## Navigation

Use Mini Program navigation semantics deliberately:

- `uni.switchTab` for root tab destinations.
- `uni.navigateTo` for detail/task flows.
- `uni.navigateBack` when returning to the previous flow is correct.
- Avoid building an in-app browser-like navigation stack.

Custom navigation should be limited to pages where the product needs it. A standard native navigation bar is preferable for ordinary detail/task pages because it preserves platform familiarity at lower implementation cost.

## Forms

- Put labels and validation close to the field.
- Keep placeholder text as an example/hint, not the only label for important data.
- Disable duplicate submission while a mutation is running.
- Keep server validation authoritative.
- For money-sensitive actions, show the amount and consequence before confirmation.

## Transactional UX

This starter is a transactional marketplace, so UI state must never be treated as payment/order truth.

Examples:

- a client-side payment callback does not finalize payment;
- a disabled claim button does not enforce single-winner claiming;
- a hidden Admin action does not replace authorization;
- a withdrawal success toast does not replace payout reconciliation.

The backend remains authoritative and idempotent; the Mini Program should surface the backend result clearly.

## Dark surfaces and future dark mode

The customer product remains light-first, while provider/workbench surfaces intentionally use dark product tokens from `theme.css`. This is **not** a global dark-mode implementation.

If global dark mode becomes a product requirement, add a complete token override at the theme layer and validate the Showcase/primitives before enabling it. Do not add unrelated page-by-page dark overrides.

## Performance / package size

- Keep the shared UI layer dependency-free.
- Prefer CSS + native controls over shipping a second full component framework.
- Keep provider-only flows in the existing subpackage.
- Do not add large icon packs for a handful of icons; use curated local assets when visual polish requires them.
- Measure before enabling heavy animation. Motion should never block task completion.

## Review checklist

For a new Mini Program page:

- [ ] Uses semantic tokens rather than arbitrary new palette values.
- [ ] Has loading, empty/error (when applicable), and content states.
- [ ] Primary action is obvious and not duplicated.
- [ ] Interactive targets have sufficient hit area.
- [ ] Bottom safe area is handled.
- [ ] Destructive or money-affecting actions require appropriate confirmation.
- [ ] Duplicate mutation submission is prevented.
- [ ] Errors provide useful recovery.
- [ ] Root-tab vs detail navigation uses the correct Mini Program API.
- [ ] Type-check and `mp-weixin` build pass.

## Validation

```bash
cd apps/miniapp
npm install
npm run ui-check
npm run type-check
npm run build:mp-weixin
npm run build:mp-weixin:staging
```

The repository CI already runs these checks for pull requests.
