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
