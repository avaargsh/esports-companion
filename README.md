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
- [ ] M2 Provider marketplace + atomic concurrent claim + service lifecycle
- [ ] M3 Settlement + ledger + realtime + Mini Program/Admin UX

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/health

The API container automatically migrates and seeds demo data. See `docs/` for the v0.1 baseline.
