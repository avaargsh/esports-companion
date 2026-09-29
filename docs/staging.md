# Staging

Staging is intentionally treated as a **secure deployment**, not as an extended
development environment.

That means `APP_ENV=staging` enforces the same security boundary as
production for:

- WeChat AuthProvider;
- WeChat PaymentProvider;
- non-default session signing key;
- HTTPS payment/refund callbacks;
- HTTPS CORS origins;
- no `/api/v1/dev/*` routes;
- no legacy `X-User-Id` / `X-Admin-Id` identity;
- no mock payment;
- no WebSocket `?user_id=` identity shortcut.

Staging remains distinguishable from production in logs/traces through
`deployment.environment.name=staging`.

## Prepare

```bash
cp .env.staging.example .env.staging
mkdir -p deploy/secrets-staging
```

Populate the dedicated staging secrets described in
`deploy/secrets-staging/README.md`.

Do not reuse production merchant/application secrets merely to make staging
easier.

Edit:

- staging Mini Program AppID;
- staging merchant identifiers;
- callback domains;
- admin origin;
- release commit SHA.

Then run:

```bash
make staging-preflight
```

The preflight deliberately rejects placeholder values and malformed secret
material before Docker starts.

## Start

```bash
make staging-up
make staging-logs
```

The staging stack reuses the hardened production Compose definition, but has a
separate Compose project name, environment file, port and secret directory.

## External endpoint boundary check

After TLS/DNS is configured:

```bash
make staging-check BASE_URL=https://api-staging.example.com
```

This verifies:

- `/livez` returns 200;
- `/readyz` returns 200;
- `/api/v1/dev/bootstrap` is not exposed;
- public ingress does not expose `/metrics`.

## Build the staging Mini Program

```bash
cp apps/miniapp/.env.staging.example apps/miniapp/.env.staging
# edit the real HTTPS API origin
make miniapp-staging-build
```

The staging build always uses `VITE_AUTH_MODE=wechat`; it cannot silently
fall back to seeded demo identity.

## Real WeChat acceptance

Repository CI cannot prove real WeChat integration without operator-controlled
credentials and a real Mini Program user. The next gate is therefore manual
but evidence-driven:

```text
real wx.login code
 -> WeChat code2Session
 -> internal session
 -> low-value JSAPI payment
 -> signed payment callback
 -> service lifecycle
 -> dispute/refund
 -> signed refund callback or reconciliation query
 -> REFUNDED
```

Record provider transaction IDs, merchant order/refund IDs, order events and
timestamps. Do not record AppSecret, APIv3 key, private key, session_key,
access tokens or refresh tokens in the evidence bundle.


## Payment client gate

The Mini Program secure build now uses the real JSAPI client path:

```text
POST /orders/{id}/payments
 -> signed JSAPI parameters
 -> wx.requestPayment
 -> verified payment callback
 -> PaymentTransaction SUCCESS
 -> PAYMENT_SUCCESS
 -> MATCHING / designated assignment
```

A successful `wx.requestPayment` callback is only a client UX signal. The
order remains `WAITING_PAYMENT` until the backend receives and verifies the
provider callback.

## Acceptance evidence

After a real low-value payment completes:

```bash
make staging-wechat-evidence \
  ORDER_ID=<order-uuid> \
  EXPECT=payment > payment-evidence.json
```

After the same acceptance order is taken through dispute/refund:

```bash
make staging-wechat-evidence \
  ORDER_ID=<order-uuid> \
  EXPECT=refund > refund-evidence.json
```

The evidence exporter intentionally omits raw callback payloads, AppSecret,
APIv3 keys, private keys, `session_key`, application tokens and JSAPI
`paySign`. It records only identifiers/status/timestamps needed to prove the
transaction path.
