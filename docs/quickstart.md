# Quick Start

This guide starts the complete demo without a WeChat AppID or merchant account.

## Prerequisites

- Docker + Docker Compose
- Python 3
- Node.js 22 + npm
- WeChat DevTools for the Mini Program client

## 1. Start the backend

```bash
cp .env.example .env
make up
```

The development stack waits for PostgreSQL/Redis, runs Alembic migrations,
seeds deterministic demo users/providers/catalog, and starts FastAPI with hot
reload.

Verify:

```text
API        http://localhost:8000
OpenAPI    http://localhost:8000/docs
Liveness   http://localhost:8000/livez
Readiness  http://localhost:8000/readyz
```

## 2. Prove the running Golden Slice

```bash
make smoke
```

This is not an in-process unit test. It calls the running API over HTTP:

```text
bootstrap
 -> create order
 -> mock payment
 -> order pool
 -> claim
 -> start
 -> finish
 -> customer confirm
 -> settlement
 -> review
 -> provider ledger verification
```

## 3. Run Admin

```bash
cd apps/admin
npm install
npm run dev
```

Open `http://localhost:5173`.

## 4. Run WeChat Mini Program

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin
```

Import `dist/dev/mp-weixin` into WeChat DevTools.

For another API host:

```bash
VITE_API_ORIGIN=http://YOUR_HOST:8000 npm run dev:mp-weixin
```

## 5. Run all build/test checks

```bash
make test
make miniapp-build
make admin-build
```

The test suite includes state-machine invariants, idempotent payment/refund and
settlement behavior, session rotation, timeout recovery, and 100-way concurrent
claim correctness.

`make test` resets the local database first so repeated runs give the same result;
local data in that database is discarded. Run `make up` afterwards to restore the
demo data.

## Demo-only boundaries

These mechanisms are deliberately unavailable in production:

- `GET /api/v1/dev/*`;
- legacy `X-User-Id` / `X-Admin-Id` identity headers;
- `POST /orders/{id}/mock-pay`.

Production uses WeChat auth + Bearer sessions + WeChat Pay provider facts.

For deployment, continue with [Production Compose](production-compose.md).
