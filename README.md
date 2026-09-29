# esports-companion

**Open-source WeChat Mini Program starter for a transactional on-demand service marketplace, with esports companion as the reference domain.**

The project focuses on the hard parts that survive beyond one vertical: order state, atomic claiming, provider assignment, payment/refund adapters, settlement/ledger, disputes, session/RBAC, realtime events and production boundaries.

```text
Customer
  -> Order
  -> WeChat / Mock Payment
  -> MATCHING
  -> Atomic Claim / Designated Provider
  -> Service Lifecycle
  -> Confirm / Auto Confirm / Dispute
  -> Settlement or Refund
  -> Ledger / Withdrawal
  -> Review
```

## Included

- **UniApp WeChat Mini Program** — customer and provider workspaces in one app
- **FastAPI modular monolith** — Auth, Catalog, Player, Order, Dispatch, Wallet, Review, Realtime
- **Web Admin** — provider verification, catalog, orders, settlement, disputes/refunds
- **PostgreSQL source of truth** — state, audit, money and idempotency
- **Redis acceleration** — reconstructable order-pool/realtime state
- **WeChat adapters** — code2Session auth, JSAPI payment, signed payment callback, refund API/callback/query reconciliation
- **Production sessions** — short access token, rotating refresh token, USER / PLAYER / PLATFORM roles
- **Money controls** — settlement ledger, withdrawals, dispute hold, refund lifecycle
- **Transactional outbox + WebSocket**
- **Production reference** — fail-fast config, file-backed secrets, health probes, structured logs, hardened non-root container/Compose
- **Prometheus + OpenTelemetry** — low-cardinality HTTP/domain metrics and optional OTLP trace export

## Core invariants

- order state changes only through domain services/state machine;
- every successful transition writes an append-only `OrderEvent`;
- PostgreSQL conditional updates/constraints provide claim correctness;
- at most one ACTIVE assignment exists for an order;
- payment success comes from verified server-side provider facts, never client UI callbacks;
- payment, settlement, withdrawal and refund paths are idempotent;
- disputes stop auto-confirm and provider settlement;
- ledger entries are money history; wallet balances are materialized query state;
- Redis is never durable order or money truth.

The concurrency acceptance suite executes **100 claim attempts against one order** and requires exactly one winner.

## Quick start: demo mode

```bash
git clone https://github.com/avaargsh/esports-companion.git
cd esports-companion
cp .env.example .env
make up
```

Verify:

```text
API        http://localhost:8000
OpenAPI    http://localhost:8000/docs
Liveness   http://localhost:8000/livez
Readiness  http://localhost:8000/readyz
```

Then execute the complete running HTTP path:

```bash
make smoke
```

Expected final output resembles:

```json
{"status":"PASS","orderId":"...","finalState":"SETTLED","providerIncome":2400}
```

See [Quick Start](docs/quickstart.md) for Mini Program and Admin startup.

## Architecture

```text
┌──────────────────────────────────────────────┐
│              WeChat Mini Program             │
│       Customer | Provider Workspace          │
└──────────────────────┬───────────────────────┘
                       │ HTTPS / WebSocket
                       ▼
┌──────────────────────────────────────────────┐
│                  FastAPI                     │
│ Auth | Catalog | Order | Dispatch | Wallet   │
│ Dispute | Refund | Review | Realtime | Admin │
└───────────────┬─────────────────┬────────────┘
                │                 │
                ▼                 ▼
          PostgreSQL            Redis
          durable truth         acceleration
                │
                ├─ OrderEvent / Outbox
                ├─ Payment / Refund
                ├─ Settlement / Ledger
                └─ Session / Audit
```

External boundaries:

```text
AuthProvider      -> Mock | WeChat code2Session
PaymentProvider   -> Mock | WeChat JSAPI
RefundProvider    -> Manual | WeChat Refund
Realtime delivery -> Transactional Outbox -> WebSocket
```

## Validation

```bash
make test
make smoke
make miniapp-build
make admin-build
```

GitHub Actions verifies independently:

```text
API          migrations + seed + lint + pytest
HTTP Smoke   real Uvicorn + Golden Slice over HTTP
MiniApp      type-check + mp-weixin build
Admin        Vite build
API Image    production build + non-root runtime + import
```

## Production deployment reference

Production mode fails closed if it sees Mock auth/payment, the development session key, missing WeChat credentials, insecure callback URLs, or localhost/insecure CORS origins.

Prepare the single-node reference:

```bash
cp .env.production.example .env.production
# populate deploy/secrets/* as documented
make prod-up
```

Production Compose:

- does **not** seed demo users;
- does **not** use `--reload`;
- does not expose PostgreSQL or Redis host ports;
- runs the API as non-root UID/GID 10001;
- mounts secrets from files;
- uses a read-only API filesystem;
- binds API to localhost by default for a TLS reverse proxy.

See [Production Readiness](docs/production-readiness.md), [Production Compose](docs/production-compose.md), and [Metrics and OpenTelemetry](docs/observability.md).

## Repository layout

```text
apps/
  miniapp/                  UniApp WeChat Mini Program
  admin/                    Vue 3 operations console

services/
  api/                      FastAPI modular monolith

deploy/
  compose/production.yml    hardened single-node reference
  secrets/README.md         required secret files

scripts/
  smoke_demo.py             real HTTP Golden Slice

docs/
  architecture.md
  order-state-machine.md
  invariants.md
  production-readiness.md
  production-compose.md
  wechat-setup.md
  wechat-refunds.md
  refund-reconciliation.md
```

## Scope

The repository is intentionally a **modular monolith**. It is suitable as a starter/reference implementation and for small deployments, but it is not presented as a security-audited turnkey platform.

Before a public launch, complete the [Release Checklist](docs/release-checklist.md), including TLS/domain configuration, WeChat merchant configuration, backup/restore testing, monitoring/alerting, ingress rate limiting and operational ownership.

## License

Apache License 2.0. See [LICENSE](LICENSE).
