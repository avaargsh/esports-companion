# Provider Adapters

External systems should not own marketplace domain semantics.

## Payment boundary

The payment path is split into:

```text
Order
  -> PaymentService
       -> PaymentProvider
            -> MockPaymentProvider
            -> WeChatPaymentProvider (next)
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

## Next production adapter

A WeChat provider should normally return a pending payment/client payload when payment is created. Durable success must be established from the verified server callback, not from the Mini Program client success callback.


## Authentication boundary

Authentication follows the same rule:

```text
Login API
  -> AuthService
       -> AuthProvider
            -> MockAuthProvider
            -> WeChatAuthProvider (next)
```

The adapter converts an external provider identity into a stable internal
`user_id`. Marketplace domains must never use `openid` as their aggregate
identifier.

The v0.2 contract already exposes:

```http
POST /api/v1/auth/wechat/login
```

In development, `AUTH_PROVIDER=mock` accepts deterministic demo codes such as
`demo-customer`. Production configuration must provide a real WeChat adapter;
the registry deliberately refuses unknown/unimplemented providers.
