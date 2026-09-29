# Runtime Modes and Production Switches

This repository has three distinct operating modes. Treat the mode boundary as a security boundary, not a convenience flag.

## Mode matrix

| Surface | Development | Staging | Production |
| --- | --- | --- | --- |
| Backend `APP_ENV` | `dev` | `staging` | `production` |
| Auth provider | `mock` | `wechat` | `wechat` |
| Payment provider | `mock` | `wechat` | `wechat` |
| Refund provider | usually `manual` | `wechat` or explicit `manual` | `wechat` or explicit `manual` |
| Legacy identity headers | allowed | disabled | disabled |
| Mock payment endpoint | allowed | disabled | disabled |
| API docs | normally enabled | disabled | disabled |
| Mini Program auth | `VITE_AUTH_MODE=demo` | `wechat` | `wechat` |
| Mini Program API | local/dev URL | public HTTPS staging URL | public HTTPS production URL |
| Admin auth | `VITE_ADMIN_AUTH_MODE=demo` | `bearer` | `bearer` |
| Admin identity | seeded PLATFORM user | PLATFORM bearer session | PLATFORM bearer session |
| Withdrawals | MANUAL operator payout | MANUAL operator payout | MANUAL operator payout until a transfer provider is implemented |

## Backend switches

### APP_ENV

`APP_ENV=staging` and `APP_ENV=production` are secure deployments.

In secure deployments the process fails closed unless:

- `AUTH_PROVIDER=wechat`;
- `PAYMENT_PROVIDER=wechat`;
- `REFUND_PROVIDER` is `wechat` or explicit `manual`;
- session signing material is not the development default;
- WeChat auth/payment credentials are configured;
- callback URLs are public HTTPS;
- CORS origins are explicit public HTTPS origins.

Secure deployments do not accept `X-User-Id` or `X-Admin-Id`, and the mock-payment compatibility path is disabled.

### Provider switches

```text
AUTH_PROVIDER=mock|wechat
PAYMENT_PROVIDER=mock|wechat
REFUND_PROVIDER=manual|wechat
```

Do not interpret `manual` refund or withdrawal handling as "fake success." It means the platform operator owns the external action while PostgreSQL, Ledger and audit state remain authoritative.

### Operational switches

```text
EXPOSE_API_DOCS=false
READINESS_REQUIRE_REDIS=true
OTEL_ENABLED=true|false
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://...
OTEL_TRACE_SAMPLE_RATIO=0.10
```

`READINESS_REQUIRE_REDIS=false` is an explicit degraded-mode decision. PostgreSQL remains mandatory.

## Mini Program switches

Local/demo build:

```bash
VITE_AUTH_MODE=demo \
VITE_API_ORIGIN=http://localhost:8000 \
npm run dev:mp-weixin
```

Staging/production build:

```bash
VITE_AUTH_MODE=wechat \
VITE_API_ORIGIN=https://api-staging.example.com \
npm run build:mp-weixin
```

In `wechat` mode:

- `uni.login` obtains a WeChat code;
- the code is exchanged for the application's access/refresh tokens;
- HTTP uses `Authorization: Bearer ...`;
- a 401 triggers one refresh-and-replay;
- WebSocket uses the same application Bearer identity;
- legacy demo identity headers are not sent.

The WeChat platform must allow the configured HTTPS request domain and WSS socket domain.

## Admin console switches

Local/demo:

```bash
VITE_ADMIN_AUTH_MODE=demo npm run dev
```

The admin console resolves the seeded PLATFORM user through `/dev/demo-identities`.

Secure staging/production:

```bash
VITE_ADMIN_AUTH_MODE=bearer \
VITE_API_BASE=https://api-staging.example.com/api/v1 \
npm run build
```

The browser must then be given a PLATFORM access token. An optional refresh token can be stored for one-session rotation.

Important boundaries:

- tokens are stored only in browser `sessionStorage`;
- no operator token belongs in `.env.production`, CI variables exposed to Vite, source control, or static assets;
- the backend still enforces the PLATFORM role on every admin endpoint;
- this is an internal operator-session boundary, not a public customer login page.

## Money-mode summary

```text
Payment
  demo       -> MockPaymentProvider
  secure     -> WeChatPaymentProvider

Refund
  manual     -> operator-owned external refund completion
  wechat     -> WeChat Refund API + callback/query reconciliation

Withdrawal
  current    -> MANUAL payout boundary
               request freezes wallet balance
               operator completes only after real payout
               reject releases frozen balance
```

There is intentionally no environment flag pretending that withdrawals are automated. A future transfer provider must replace the external payout boundary without bypassing Wallet/Ledger invariants.

## Release rule

A release is not production-ready merely because the application builds.

At minimum:

1. secure deployment config must pass;
2. Mini Program must be built in `wechat` mode;
3. Admin must be built in `bearer` mode;
4. staging login/payment/refund must exercise real provider paths;
5. withdrawal ownership must be assigned to an operator;
6. smoke, backup/restore, ingress, metrics and image checks must be green.
