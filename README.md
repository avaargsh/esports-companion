# esports-companion

Open-source **WeChat Mini Program esports companion marketplace starter**.

## Golden Slice

```text
Create Order -> Mock Payment -> MATCHING -> Order Pool -> Concurrent Claim
-> Service Lifecycle -> Settlement -> Ledger -> Review
```

v0.1 uses a Modular Monolith: **PostgreSQL owns durable truth; Redis only accelerates runtime state.**

## Milestones

- [x] M0 FastAPI / PostgreSQL / Redis / Alembic / CI skeleton
- [x] M1 Game + SKU + Create Order + Mock Payment + MATCHING
- [x] M2 Provider marketplace + atomic concurrent claim + service lifecycle
- [x] M3 Settlement + ledger + realtime + Mini Program/Admin UX

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/health

The API container automatically migrates and seeds demo data. See `docs/` for the v0.1 baseline.


## Run the clients

WeChat Mini Program:

```bash
cd apps/miniapp
npm install
npm run dev:mp-weixin
```

Admin Console:

```bash
cd apps/admin
npm install
npm run dev
```

The Mini Program uses Mock WeChat identity and Mock Payment in development. Admin runs at http://localhost:5173 and reads the seeded demo administrator automatically.

## Acceptance

`make test` includes the full HTTP Golden Slice plus the 100-concurrent-claim invariant.

See:

- `docs/acceptance.md`
- `docs/realtime.md`
- `docs/invariants.md`
