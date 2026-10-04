# Admin Operations Console

Vue 3 internal operations console for the marketplace.

## Product navigation

v0.5 intentionally exposes only five top-level domains:

```text
Overview
Orders
Players
Finance
Configuration
```

Existing capabilities are nested instead of deleted:

- **Overview**: SLA operations queue + marketplace metrics.
- **Orders**: order lookup, evidence, dispute and refund handling.
- **Players**: player application review + skill/evidence review.
- **Finance**: withdrawals, payout evidence and settlements.
- **Configuration**: game + service SKU catalog.

The backend still keeps OrderEvent, Settlement, Ledger, Refund, Withdrawal,
Outbox and Evidence as durable operational facts. They are not separate product
navigation concepts.

## Local real-account mode

Start the FastAPI backend first, then:

```bash
cd apps/admin
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. The console defaults to Bearer
auth and no longer requires demo identities. Admin login uses WeChat Open
Platform website QR login (`snsapi_login`); configure `WECHAT_WEB_APP_ID`,
`WECHAT_WEB_APP_SECRET` or `WECHAT_WEB_APP_SECRET_FILE`, and
`WECHAT_WEB_REDIRECT_URI`. The scanned WeChat identity must resolve by `unionid`
to an active user whose `users.role` is `PLATFORM`.

For local browser testing, expose the admin dev server through a public HTTPS
domain that is configured as the WeChat Open Platform callback domain, then set
`WECHAT_WEB_REDIRECT_URI` to that admin URL. The fallback Token panel remains
available for already issued PLATFORM access tokens.

## Optional local demo mode

Demo mode is only for seeded development data:

```bash
VITE_ADMIN_AUTH_MODE=demo npm run dev
```

## Secure staging / production mode

Secure deployments reject legacy admin headers. Build the console in Bearer
mode:

```bash
VITE_ADMIN_AUTH_MODE=bearer \
VITE_API_BASE=https://api-staging.example.com/api/v1 \
npm run build
```

At runtime the operator logs in with WeChat and the backend only accepts accounts
with the PLATFORM role. A refresh token enables session rotation after a 401.

Security boundary:

- operator tokens are kept in browser `sessionStorage`;
- do not embed access/refresh tokens in Vite environment variables or static
  build artifacts;
- every admin API verifies the PLATFORM role server-side;
- clearing the session removes the local operator token.

See [Product Simplification](../../docs/product-simplification.md),
[Runtime Modes](../../docs/runtime-modes.md) and
[Operations](../../docs/operations.md).
