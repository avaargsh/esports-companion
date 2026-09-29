# API v0.1

## Customer

- GET /health
- GET /api/v1/games
- GET /api/v1/games/{gameId}/skus
- POST /api/v1/orders
- GET /api/v1/orders/{orderId}
- POST /api/v1/orders/{orderId}/mock-pay
- POST /api/v1/orders/{orderId}/cancel
- POST /api/v1/orders/{orderId}/confirm
- POST /api/v1/orders/{orderId}/reviews
- GET /api/v1/wallet
- GET /api/v1/wallet/ledger

Development customer auth uses `X-User-Id`.

## Player

- POST /api/v1/player/apply
- GET /api/v1/player/profile
- PATCH /api/v1/player/profile
- GET /api/v1/player/order-pool
- POST /api/v1/player/orders/{orderId}/claim
- POST /api/v1/player/orders/{orderId}/start
- POST /api/v1/player/orders/{orderId}/finish

Claim requires the current order `expected_version`.

## Admin

- GET /api/v1/admin/players
- POST /api/v1/admin/players/{id}/approve
- POST /api/v1/admin/players/{id}/reject
- GET /api/v1/admin/orders
- GET /api/v1/admin/settlements

Demo admin auth uses `X-Admin-Id` for a PLATFORM/ADMIN user.

## Realtime

- WS /ws

See `docs/realtime.md`.
