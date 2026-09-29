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

## Local demo mode

Start the FastAPI backend first, then:

```bash
cd apps/admin
npm install
VITE_ADMIN_AUTH_MODE=demo npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

## Secure staging / production mode

Secure deployments reject legacy admin headers. Build the console in Bearer
mode:

```bash
VITE_ADMIN_AUTH_MODE=bearer \
VITE_API_BASE=https://api-staging.example.com/api/v1 \
npm run build
```

At runtime the operator enters a PLATFORM access token into the session panel.
A refresh token is optional and enables session rotation after a 401.

Security boundary:

- operator tokens are kept in browser `sessionStorage`;
- do not embed access/refresh tokens in Vite environment variables or static
  build artifacts;
- every admin API verifies the PLATFORM role server-side;
- clearing the session removes the local operator token.

See [Product Simplification](../../docs/product-simplification.md),
[Runtime Modes](../../docs/runtime-modes.md) and
[Operations](../../docs/operations.md).
