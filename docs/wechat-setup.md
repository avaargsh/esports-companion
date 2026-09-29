# WeChat Production Integration

Development defaults to Mock Auth/Payment so the marketplace can be evaluated without third-party credentials. Production adapters for WeChat login, JSAPI payment, verified callbacks, refunds, and refund reconciliation are implemented behind provider boundaries.

## Authentication

Development:

```text
Mini Program -> Demo Identity -> internal user_id
```

Production path:

```text
wx.login()
  -> code
  -> POST /api/v1/auth/wechat/login
  -> WeChat code2Session
  -> openid / unionid mapping
  -> internal user_id
  -> application session/token
```

Only the auth adapter should know about `openid`, `unionid` and `session_key`.
Order, wallet, dispatch and review modules should continue using the internal `user_id`.

The Mini Program production client uses `VITE_AUTH_MODE=wechat`. It persists
only the application's access/refresh token pair, never the WeChat
`session_key`. Authenticated HTTP calls use a Bearer access token. Access
tokens are refreshed with refresh-token rotation; a 401 triggers at most one
refresh-and-replay of the original request.

Realtime uses the same application identity:

```text
wx.login -> app session
              |
              +-> HTTP Authorization: Bearer <access>
              |
              +-> WSS /ws
                  Authorization: Bearer <access>
```

The development-only `X-User-Id` and `/ws?user_id=...` compatibility paths
remain available only when the backend is not a secure deployment.

## Payment

Development:

```text
POST /orders/{id}/mock-pay
  -> PaymentTransaction SUCCESS
  -> PAID
  -> MATCHING
```

Production flow:

```text
POST /orders/{id}/payments
  -> backend creates/replays a WeChat JSAPI prepay attempt
  -> signed client payload
  -> uni.requestPayment()
  -> WeChat callback
  -> verify signature + decrypt provider resource
  -> idempotent PaymentTransaction SUCCESS
  -> order state machine
  -> PAID -> MATCHING / designated ACCEPTED
```

The client-side `uni.requestPayment` success callback is intentionally not
durable payment truth. The Mini Program briefly reloads the order and then
waits for the signed provider callback through normal HTTP/WebSocket state
updates.

## Required production configuration

Required production identifiers/providers (sensitive values should use the documented `*_FILE` secret mounts):

```text
APP_ENV=production
AUTH_PROVIDER=wechat
PAYMENT_PROVIDER=wechat
REFUND_PROVIDER=wechat

WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
WECHAT_MCH_ID=...
WECHAT_MCH_CERT_SERIAL=...
WECHAT_MCH_PRIVATE_KEY=...
WECHAT_PAY_API_V3_KEY=...
WECHAT_NOTIFY_URL=https://api.example.com/api/v1/payments/wechat/callback
WECHAT_REFUND_NOTIFY_URL=https://api.example.com/api/v1/refunds/wechat/callback
```

Secrets must not be committed to the repository.

## Network requirements

A released Mini Program needs HTTPS request/socket domains configured in the WeChat platform. Replace local development origins with your production API and WebSocket origins.

## Subscription messages

Order domain events are already written to the transactional outbox. A production notification adapter can map events such as:

- `PLAYER_CLAIMED`
- `SERVICE_STARTED`
- `FINISH_REQUESTED`
- `SETTLEMENT_COMPLETED`

to WeChat subscription messages without moving WeChat-specific logic into the order domain.
