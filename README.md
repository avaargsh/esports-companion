# esports-companion

**Open-source WeChat Mini Program starter for an on-demand esports companion marketplace.**

It is intentionally built around a reusable marketplace core rather than a pile of companion-specific CRUD pages.

```text
Customer
   |
Create Order
   |
Mock / WeChat Payment
   v
MATCHING -> Order Pool -> Atomic Claim -> Assignment
                              |
                              v
                         Service Lifecycle
                              |
                              v
                         Settlement
                         /        \
                Provider Ledger  Platform Ledger
                              |
                              v
                            Review
```

## What is included

- **WeChat Mini Program** — customer workspace + player workspace in one app
- **FastAPI modular monolith** — Catalog, Player, Order, Dispatch, Wallet, Review, Realtime
- **PostgreSQL** — durable source of truth
- **Redis** — order pool, presence/cache/runtime acceleration only
- **Web Admin** — player review, order operations, settlement view
- **WebSocket + Outbox** — realtime order status delivery
- **Mock Auth / Mock Payment** — clone and run without WeChat credentials
- **CI acceptance** — API, Mini Program and Admin builds

## Engineering highlights

The project demonstrates several invariants that are easy to lose in a CRUD marketplace:

- explicit order state machine;
- optimistic concurrency with `orders.version`;
- PostgreSQL conditional update for atomic claim;
- at most one ACTIVE `OrderAssignment`;
- append-only `OrderEvent` audit timeline;
- transactional outbox for realtime side effects;
- idempotent payment and settlement;
- ledger-based money history;
- Redis treated as reconstructable state, never order truth.

The concurrency acceptance test starts **100 claim attempts against one order** and requires exactly one success.

## Architecture

```text
┌─────────────────────────────────────────────┐
│              WeChat Mini Program            │
│     Customer Workspace | Player Workspace   │
└──────────────────────┬──────────────────────┘
                       │ HTTPS / WebSocket
                       v
┌─────────────────────────────────────────────┐
│                  FastAPI                    │
│ Auth | Catalog | Player | Order | Dispatch  │
│ Wallet | Review | Realtime | Admin          │
└───────────────┬─────────────────┬───────────┘
                │                 │
                v                 v
          PostgreSQL            Redis
          source of truth       acceleration
                │
                v
     OrderEvent + Transactional Outbox

                 Web Admin
                    |
                    +------> FastAPI
```

## Five-minute backend start

```bash
git clone https://github.com/avaargsh/esports-companion.git
cd esports-companion
cp .env.example .env
docker compose up --build
```

Then:

- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

The API container runs migrations and seeds demo identities, approved players, games and SKUs.

For the complete Mini Program/Admin workflow, see **[docs/quickstart.md](docs/quickstart.md)**.

## Golden Slice

```text
Create Order
 -> Mock Payment
 -> MATCHING
 -> Order Pool
 -> Concurrent Claim
 -> ACCEPTED
 -> Start
 -> IN_SERVICE
 -> Finish Request
 -> Customer Confirm
 -> Settlement
 -> Ledger
 -> Review
```

The full path is executable through `services/api/tests/test_golden_slice_e2e.py`.

## Current status

- [x] M0 — FastAPI / PostgreSQL / Redis / Alembic / CI
- [x] M1 — Game/SKU → Create → Mock Pay → MATCHING
- [x] M2 — Provider → Pool → atomic claim → service lifecycle
- [x] M3 — Settlement/Ledger → Review → Realtime → Mini Program → Admin

**v0.1 scope is frozen around this vertical slice.** Real WeChat login and WeChat Pay are adapters for the next productionization step, not blockers for the open-source demo.

## Repository layout

```text
apps/
  miniapp/                 UniApp WeChat Mini Program
  admin/                   Vue 3 operations console

services/
  api/                     FastAPI modular monolith

domain-packs/
  esports-companion/       esports reference configuration

docs/
  architecture.md
  domain-model.md
  order-state-machine.md
  invariants.md
  golden-slice.md
  acceptance.md
  realtime.md
  quickstart.md
  wechat-setup.md
```

## Validation

```bash
make test
make miniapp-build
make admin-build
```

GitHub Actions independently verifies:

```text
API        migrations + lint + pytest + Golden Slice
MiniApp    npm install + vue-tsc + mp-weixin build
Admin      npm install + Vite build
```

## Production boundaries

The repository defaults to Demo Mode.

Do **not** treat these as production auth/payment mechanisms:

- `X-User-Id`
- `X-Admin-Id`
- `/api/v1/dev/*`
- `/orders/{id}/mock-pay`

See [docs/wechat-setup.md](docs/wechat-setup.md) for the intended WeChat adapter boundaries.

## Documentation

- [Quick Start](docs/quickstart.md)
- [Architecture](docs/architecture.md)
- [Domain Model](docs/domain-model.md)
- [Order State Machine](docs/order-state-machine.md)
- [Core Invariants](docs/invariants.md)
- [Golden Slice](docs/golden-slice.md)
- [Acceptance Tests](docs/acceptance.md)
- [Realtime / Outbox](docs/realtime.md)
- [API](docs/api.md)
- [WeChat Production Integration](docs/wechat-setup.md)

## License

Apache License 2.0. See [LICENSE](LICENSE).
