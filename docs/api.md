# API

Production clients authenticate with:

```http
Authorization: Bearer <access-token>
```

Development/test may still use `X-User-Id` / `X-Admin-Id`.

## Auth

- POST /api/v1/auth/wechat/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET /api/v1/auth/me

## Public Catalog

- GET /api/v1/games
- GET /api/v1/games/{gameId}/skus

Only ACTIVE games and SKUs are exposed publicly.

## Customer

- POST /api/v1/orders
- GET /api/v1/orders
- GET /api/v1/orders/{orderId}
- POST /api/v1/orders/{orderId}/payments
- POST /api/v1/orders/{orderId}/mock-pay
- POST /api/v1/orders/{orderId}/cancel
- POST /api/v1/orders/{orderId}/confirm
- POST /api/v1/orders/{orderId}/reviews
- GET /api/v1/wallet
- GET /api/v1/wallet/ledger

`mock-pay` is disabled in production.

## Player

- POST /api/v1/player/apply
- GET /api/v1/player/profile
- PUT /api/v1/player/profile
- GET /api/v1/player/order-pool
- GET /api/v1/player/orders
- POST /api/v1/player/orders/{orderId}/claim
- POST /api/v1/player/orders/{orderId}/start
- POST /api/v1/player/orders/{orderId}/finish
- GET /api/v1/player/offerings
- PUT /api/v1/player/offerings/{skuId}

Claim requires:

- APPROVED player;
- AVAILABLE service state;
- ACTIVE ProviderOffering for the order SKU;
- current order `expected_version`.

## Admin

- GET /api/v1/admin/players
- POST /api/v1/admin/players/{id}/approve
- POST /api/v1/admin/players/{id}/reject
- GET /api/v1/admin/orders
- GET /api/v1/admin/settlements

Catalog Admin:

- GET /api/v1/admin/catalog/games
- POST /api/v1/admin/catalog/games
- PATCH /api/v1/admin/catalog/games/{gameId}
- GET /api/v1/admin/catalog/skus
- POST /api/v1/admin/catalog/skus
- PATCH /api/v1/admin/catalog/skus/{skuId}

All admin APIs require PLATFORM role in production.

## Payment callback

- POST /api/v1/payments/wechat/callback

The callback verifies WeChat signature, decrypts the APIv3 resource, applies
payment idempotently, then transitions the order into PAID -> MATCHING.

## Realtime

- WS /ws

See `docs/realtime.md`.
