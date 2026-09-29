# WeChat Mini Program

Target stack: UniApp + Vue 3 + TypeScript.

One Mini Program contains both Customer and Player workspaces.

## Local development

1. Start backend from repository root:

```bash
cp .env.example .env
docker compose up --build
```

2. Install and build the Mini Program:

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin
```

3. Import `dist/dev/mp-weixin` in WeChat DevTools.

The default API origin is `http://localhost:8000`. Override it with:

```bash
VITE_API_ORIGIN=http://YOUR_HOST:8000 npm run dev:mp-weixin
```

Demo mode auto-discovers seeded Customer / Player identities. No WeChat AppID or payment merchant account is required for the Golden Slice.

## Demo flow

```text
Customer: Home -> Game -> Create -> Pay
Player: Workbench -> Order Pool -> Claim -> Start -> Finish
Customer: Order Detail -> Confirm -> Settlement -> Review
```


## WeChat staging / production auth

Local development defaults to:

```text
VITE_AUTH_MODE=demo
```

This keeps the seeded `X-User-Id` development workflow.

For a secure staging or production Mini Program build, use the real API origin
and WeChat session mode:

```bash
VITE_AUTH_MODE=wechat \
VITE_API_ORIGIN=https://api-staging.example.com \
npm run build:mp-weixin
```

In `wechat` mode the Mini Program:

1. calls `uni.login({ provider: "weixin" })`;
2. exchanges the code through `POST /api/v1/auth/wechat/login`;
3. persists the application access/refresh token pair in Mini Program storage;
4. sends authenticated API requests with `Authorization: Bearer ...`;
5. rotates the refresh token when the access token is near expiry or an
   authenticated request returns 401;
6. authenticates `/ws` using the same Bearer access token;
7. prepares JSAPI payment through `POST /orders/{id}/payments`;
8. invokes `wx.requestPayment` with server-signed parameters;
9. waits for the verified WeChat callback to move the order out of
   `WAITING_PAYMENT`.

The client-side `requestPayment.success` callback is **not** treated as durable
payment truth. The UI only shows “payment confirmed” after canonical order state
has changed on the server.

Legacy `X-User-Id`, `X-Admin-Id`, and `/ws?user_id=...` are never sent by
the client in `wechat` mode.

The released Mini Program must configure the HTTPS request domain and WSS
socket domain in the WeChat platform.


## Product paths

Customer:

```text
Home
  -> Game / pooled service
  -> Discover verified player
  -> Player profile / Offering
  -> designated order
  -> payment / fulfillment / chat / evidence / aftercare
```

Player:

```text
Workbench
  -> order pool / service orders
  -> Offering + Skill management
  -> settled Wallet balance
  -> withdrawal request / history
```

Withdrawals currently use a MANUAL payout boundary. Submitting a withdrawal freezes available balance; the platform operator only marks it complete after an actual external payout.

See [Runtime Modes](../../docs/runtime-modes.md) for dev/staging/production switches.


## Staging build

Prepare once:

```bash
cp apps/miniapp/.env.staging.example apps/miniapp/.env.staging
# edit VITE_API_ORIGIN to the real staging HTTPS origin
```

Then build from the repository root:

```bash
make miniapp-staging-build
```

This runs UniApp in Vite `staging` mode with `VITE_AUTH_MODE=wechat`.
Import `apps/miniapp/dist/build/mp-weixin` into WeChat DevTools using the
staging Mini Program AppID. Configure the request and socket domains before
testing real login/payment.
