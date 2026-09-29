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
