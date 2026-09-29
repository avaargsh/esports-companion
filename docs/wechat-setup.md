# WeChat Production Integration

v0.1 intentionally runs with Mock Auth and Mock Payment so the marketplace domain can be evaluated without third-party credentials.

## Authentication

Development:

```text
Mini Program -> Demo Identity -> internal user_id
```

Production target:

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

## Payment

Development:

```text
POST /orders/{id}/mock-pay
  -> PaymentTransaction SUCCESS
  -> PAID
  -> MATCHING
```

Production target:

```text
Create payment
  -> backend creates WeChat Pay order
  -> wx.requestPayment()
  -> WeChat callback
  -> verify callback/signature
  -> idempotent PaymentTransaction
  -> order state machine
  -> PAID -> MATCHING
```

The client-side payment success callback must not be treated as durable payment truth.

## Required production configuration

Recommended environment variables:

```text
APP_ENV=production
AUTH_PROVIDER=wechat
PAYMENT_PROVIDER=wechat

WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
WECHAT_MCH_ID=...
WECHAT_MCH_CERT_SERIAL=...
WECHAT_MCH_PRIVATE_KEY=...
WECHAT_PAY_API_V3_KEY=...
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
