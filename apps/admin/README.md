# Admin Operations Console

Vue 3 internal operations console for the marketplace.

Current queues:

- Dashboard / transaction overview
- Player application review
- Skill/evidence review
- Catalog management
- Order lookup
- Dispute/refund workbench
- Withdrawal review and manual-payout confirmation
- Settlement inspection

## Local demo mode

Start the FastAPI backend first, then:

```bash
cd apps/admin
npm install
VITE_ADMIN_AUTH_MODE=demo npm run dev
```

Vite proxies `/api` to `http://localhost:8000`. Demo mode discovers the seeded PLATFORM identity and uses the development-only `X-Admin-Id` compatibility path.

## Secure staging / production mode

Secure deployments reject legacy admin headers. Build the console in Bearer mode:

```bash
VITE_ADMIN_AUTH_MODE=bearer \
VITE_API_BASE=https://api-staging.example.com/api/v1 \
npm run build
```

At runtime the operator enters a PLATFORM access token into the session panel. A refresh token is optional and enables session rotation after a 401.

Security boundary:

- operator tokens are kept in browser `sessionStorage`;
- do not embed access/refresh tokens into Vite environment variables or static build artifacts;
- every admin API still verifies the PLATFORM role server-side;
- clearing the session removes the local operator token.

See [Runtime Modes](../../docs/runtime-modes.md) and [Operations](../../docs/operations.md).
