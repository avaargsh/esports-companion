# Quick Start

This guide gets the complete v0.1 demo running without a WeChat AppID or payment merchant account.

## Prerequisites

- Docker + Docker Compose
- Node.js 22
- npm
- WeChat DevTools for the Mini Program client

## 1. Start the backend

From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

The API container automatically:

1. waits for PostgreSQL and Redis;
2. runs Alembic migrations;
3. seeds demo users, approved players, games and SKUs;
4. starts FastAPI.

Verify:

```text
API       http://localhost:8000
OpenAPI   http://localhost:8000/docs
Health    http://localhost:8000/health
```

## 2. Run the Admin Console

```bash
cd apps/admin
npm install
npm run dev
```

Open `http://localhost:5173`.

The development console discovers the seeded demo administrator automatically.

## 3. Run the WeChat Mini Program

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin
```

Import the generated `dist/dev/mp-weixin` directory into WeChat DevTools.

For a backend running on another host:

```bash
VITE_API_ORIGIN=http://YOUR_HOST:8000 npm run dev:mp-weixin
```

## 4. Walk the Golden Slice

Customer workspace:

```text
Home
  -> choose game
  -> choose SKU
  -> Create Order
  -> Mock Pay
  -> MATCHING
```

Player workspace:

```text
Workbench
  -> Order Pool
  -> Claim
  -> ACCEPTED
  -> Start
  -> IN_SERVICE
  -> Finish
  -> FINISH_REQUESTED
```

Customer workspace again:

```text
Order Detail
  -> Confirm
  -> COMPLETED
  -> automatic Settlement
  -> SETTLED
  -> Review
```

The player's wallet receives the provider share and the platform wallet receives the platform fee.

## 5. Run acceptance tests

```bash
make test
```

The suite includes:

- full HTTP Golden Slice;
- 100 concurrent claim attempts with exactly one winner;
- payment idempotency;
- settlement idempotency;
- state-machine invariants.

## Demo-only endpoints

The following exist only outside production:

- `GET /api/v1/dev/demo-identities`
- `GET /api/v1/dev/bootstrap`

Do not build production authentication around these endpoints.
