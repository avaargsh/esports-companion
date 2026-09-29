# Provider Adapters

External systems should not own marketplace domain semantics.

## Payment boundary

The payment path is split into:

```text
Order
  -> PaymentService
       -> PaymentProvider
            -> MockPaymentProvider
            -> WeChatPaymentProvider
```

`PaymentProvider` creates provider-side payment intent/result data.

`PaymentService` owns durable application semantics:

- idempotency lookup;
- `PaymentTransaction` persistence;
- transition into `PAID`;
- transition into `MATCHING`;
- associated OrderEvent / Outbox events.

This means a WeChat adapter should verify provider-specific callbacks and feed verified payment facts into the same application service rather than mutating `orders.status` directly.

## Current provider

v0.1/v0.2 baseline includes `MockPaymentProvider`.

It is synchronous and returns `SUCCESS`, which keeps the local Golden Slice credential-free.

## WeChat payment adapter

`WeChatPaymentProvider` implements the JSAPI/Mini Program prepayment boundary:

```text
PaymentService.prepare_payment
  -> WeChat unified order
  -> prepay_id
  -> timeStamp / nonceStr / package / signType / paySign
  -> Mini Program requestPayment()
```

The resulting `PaymentTransaction` remains `PENDING`, and the marketplace
order remains `WAITING_PAYMENT`. Client payment success is intentionally not
treated as durable truth. The next dependency is verified payment callback
processing, which alone may move the order into `PAID -> MATCHING`.

The generic endpoint is:

```http
POST /api/v1/orders/{order_id}/payments
Idempotency-Key: ...
```

It uses the configured `PAYMENT_PROVIDER` and returns the provider-specific
client payload without exposing provider implementation details to the order
domain.


## Authentication boundary

Authentication follows the same rule:

```text
Login API
  -> AuthService
       -> AuthProvider
            -> MockAuthProvider
            -> WeChatAuthProvider
```

The adapter converts an external provider identity into a stable internal
`user_id`. Marketplace domains must never use `openid` as their aggregate
identifier.

The v0.2 contract already exposes:

```http
POST /api/v1/auth/wechat/login
```

In development, `AUTH_PROVIDER=mock` accepts deterministic demo codes such as
`demo-customer`.

With `AUTH_PROVIDER=wechat`, `WeChatAuthProvider` exchanges the Mini Program
login code through WeChat code2Session and maps the returned `openid` /
`unionid` to the internal `user_id`. The returned `session_key` remains
server-side provider session material: it is never returned as the application's
authentication token and is not used as a marketplace aggregate identifier.

Required settings:

```text
AUTH_PROVIDER=wechat
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
```

Unknown providers and missing WeChat credentials fail closed.


## Verified WeChat payment callback

The callback path is intentionally separate from payment creation:

```text
POST /api/v1/payments/wechat/callback
  -> verify Wechatpay-* signature over exact raw body
  -> enforce platform certificate serial + timestamp window
  -> AES-256-GCM decrypt resource with APIv3 key
  -> validate appid / mchid / amount / out_trade_no
  -> find PENDING PaymentTransaction
  -> replace prepay_id with provider transaction_id
  -> status SUCCESS
  -> order PAID -> MATCHING
  -> OrderEvent + Outbox
  -> reconstruct Redis order pool best-effort
```

Duplicate callbacks are idempotent through the existing
`(provider, provider_txn_id)` uniqueness and application-level replay handling.

The Mini Program success callback is never authoritative for payment state.
