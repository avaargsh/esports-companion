# WeChat Mini Program Frontend Design v0.1

## Product shell

One Mini Program, two workspaces:

- **Customer main package**: bright marketplace UI for discovery, order, payment, realtime status and review.
- **Player subpackage**: dark operational UI for order pool, fulfillment and earnings.

The two roles share identity and deployment, but not the same information hierarchy.

## Customer journey

`Home -> Game/SKU -> Create -> Pay -> MATCHING -> ACCEPTED -> IN_SERVICE -> FINISH_REQUESTED -> SETTLED -> Review`

Primary tabs remain **Home / Orders / Profile**.

Customer UI intentionally does not expose `player_amount` or `platform_fee`. Those values belong to settlement and player operations, not the customer decision surface.

## Player journey

`Profile/Home -> Workbench -> Order Pool -> Claim -> Service Orders -> Start -> Finish -> Wait for Customer -> Wallet`

Player pages prioritize:

1. availability / service status
2. available and frozen earnings
3. pending fulfillment
4. claim and lifecycle actions

Marketing modules stay out of the operational workspace.

## State contract

The frontend does not invent a second order state machine. All labels and progress derive from backend states:

`WAITING_PAYMENT -> PAID -> MATCHING -> ACCEPTED -> IN_SERVICE -> FINISH_REQUESTED -> COMPLETED -> SETTLED`

Exceptional states:

`CANCELLED / REFUNDING / REFUNDED / DISPUTED`

WebSocket `order.status_changed` is only an invalidation signal. The client reloads canonical order state from the API instead of treating event payloads as the source of truth.

## Visual direction

### Customer

- neutral #F6F7FB background
- white transaction cards
- purple primary action
- green only for success / online semantics
- human-readable Chinese order states and visible lifecycle progress
- restrained gaming identity instead of cyberpunk decoration

### Player

- dark workbench
- earnings and fulfillment state above decorative content
- purple is reserved for executable primary actions

## v0.1 acceptance

The existing Golden Slice should remain buildable and complete:

1. Customer selects game and SKU.
2. Customer creates and mock-pays an order.
3. Order enters MATCHING and appears in Player order pool.
4. Player claims and starts service.
5. Player requests finish.
6. Customer sees realtime status and confirms completion.
7. Settlement updates Player wallet.
8. Customer gives a 1–5 star review with optional text.

## Next slice

- real WeChat login / account binding
- WebSocket auth, reconnect and heartbeat
- player profile / rating / recommendation APIs
- wallet ledger page
- refund / dispute / customer-service UI
- skeleton, retry and accessibility polish
- real payment adapter
