# Mini Program Experience Design

Branch: `frontend/miniapp-experience`

## Visual direction

The Mini Program uses a calm marketplace visual language instead of a
game-themed dashboard aesthetic:

- warm neutral canvas;
- ink-black text and primary actions;
- violet brand accent;
- mint success state;
- large but consistent radii;
- subtle shadows used only to separate interactive surfaces;
- strong numeric hierarchy for prices and earnings.

Customer pages stay bright. Player operations use the same spacing/status
system on a dark surface.

## Interaction rules

1. One screen, one dominant job.
2. Primary actions are at least 84rpx high.
3. Customer navigation stays Home / Orders / Profile.
4. Discovery uses one filter layer only.
5. Order state is always more visually prominent than implementation details.
6. Empty/loading/error states are explicit and actionable.
7. Technical terms such as SKU, Provider, SLA and Ledger never appear in
   customer-facing copy.
8. Payment success is not declared until canonical server state changes.

## Component primitives

- `SectionHeader`: title, supporting copy and optional action.
- `PlayerCard`: verified identity, live presence, trust signals and entry price.
- `EmptyState`: consistent loading/error/no-data recovery surface.
- `OrderCard`: state-first order summary.
- `PrimaryActionBar`: fixed safe-area-aware transactional action bar.

The pages should compose these primitives rather than redefining the same card
language independently.


## Mobile shell hardening

The UX branch now treats safe areas and transactional controls as shared
infrastructure:

- custom tab pages use the UniApp status-bar CSS variable instead of fixed top
  padding;
- quick-match and designated-player purchase flows share one CheckoutBar;
- service selection has explicit loading, error and empty states;
- the checkout control always shows total price plus the currently selected
  service;
- order filters surface category counts to reduce unnecessary taps.

The goal is consistent behavior on real devices, not a larger component
catalog.


## Language cleanup

The player workspace uses product language rather than internal platform
language:

- “接单市场” instead of “LIVE MARKET”;
- “服务进展” instead of “履约证据”;
- “收益账户” instead of “PLAYER WALLET”;
- role/event labels are localized for the person using the screen;
- the order pool emphasizes expected income and service quantity rather than
  platform fee internals.

Operational evidence still exists in the backend; the Mini Program only exposes
what helps the current action.


## Attention budget

Order detail pages reserve visual emphasis for the current state and the next
action:

- healthy realtime connectivity is silent;
- connectivity problems appear as a small recoverable warning;
- only the latest four order events are shown by default;
- full audit/event history is one tap away;
- financial sections use customer/player language rather than duplicating
  backend object names.

The backend retains complete evidence. The UI reveals detail progressively.
