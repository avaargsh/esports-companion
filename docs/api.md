# API v0.1

M1 endpoints:

- GET /health
- GET /api/v1/games
- GET /api/v1/games/{gameId}/skus
- POST /api/v1/orders
- GET /api/v1/orders/{orderId}
- POST /api/v1/orders/{orderId}/mock-pay
- POST /api/v1/orders/{orderId}/cancel

Development auth uses `X-User-Id`. Payment mutation requires `Idempotency-Key`.
