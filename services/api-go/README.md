# api-go

Go backend migration target and reusable high-throughput API foundation.

This service is intentionally introduced beside the existing FastAPI service. It is
**not** a second product backend and must not create a second source of truth.

## Goals

- keep PostgreSQL as durable truth and Redis as reconstructable acceleration;
- preserve the existing `/api/v1` contracts while modules migrate;
- keep Auth / Payment / Refund behind provider ports;
- preserve idempotency, transaction boundaries and append-only evidence;
- use a modular monolith until profiling proves a real split boundary;
- provide low-overhead HTTP, pgx pooling, Redis pooling, Prometheus metrics and structured logs.

## Stack

- Go 1.27
- `net/http` + `chi`
- `pgx/v5`
- `go-redis/v9`
- Prometheus client
- standard `log/slog`

## Run

The Go service defaults to `:8080` so it can run beside the Python API on `:8000`.

```bash
cd services/api-go
go mod download
go test -race ./...
go run ./cmd/api

# Background runtime (currently transactional outbox publisher)
go run ./cmd/worker
```

It accepts the existing environment variables:

```text
APP_ENV
SERVICE_NAME
COMMIT_SHA
LOG_LEVEL
DATABASE_URL / DATABASE_URL_FILE
REDIS_URL / REDIS_URL_FILE
READINESS_REQUIRE_REDIS
AUTH_PROVIDER
PAYMENT_PROVIDER
REFUND_PROVIDER
SESSION_SIGNING_KEY / SESSION_SIGNING_KEY_FILE
ACCESS_TOKEN_TTL_SECONDS
REFRESH_TOKEN_TTL_SECONDS
WECHAT_APP_ID
WECHAT_APP_SECRET / WECHAT_APP_SECRET_FILE
WECHAT_AUTH_TIMEOUT_SECONDS
```

Pool tuning:

```text
DATABASE_MAX_CONNS=32
DATABASE_MIN_CONNS=4
REDIS_POOL_SIZE=64
API_GO_HTTP_ADDR=:8080
SHUTDOWN_TIMEOUT_SECONDS=15
OUTBOX_POLL_INTERVAL_MS=500
OUTBOX_BATCH_SIZE=50
```

The loader accepts the current Python-style
`postgresql+psycopg://...` URL and normalizes it for pgx.

## Endpoints

- `GET /livez`
- `GET /readyz`
- `GET /metrics`
- `GET /api/v1/runtime`
- `POST /api/v1/auth/wechat/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/games`
- `GET /api/v1/games/{game_id}/skus`
- `GET /api/v1/players`
- `GET /api/v1/players/{player_id}`
- `GET /api/v1/orders`
- `POST /api/v1/orders`
- `POST /api/v1/player/orders/{order_id}/claim`
- `GET /api/v1/orders/{order_id}`
- `GET /api/v1/orders/{order_id}/events`
- `POST /api/v1/player/orders/{order_id}/claim`
- `POST /api/v1/player/orders/{order_id}/start`
- `POST /api/v1/player/orders/{order_id}/finish`
- `POST /api/v1/orders/{order_id}/confirm`
- `POST /api/v1/orders/{order_id}/mock-pay`
- `POST /api/v1/orders/{order_id}/payments`
- `POST /api/v1/payments/wechat/callback`
- `POST /api/v1/admin/refunds/{refund_id}/submit`
- `POST /api/v1/admin/refunds/{refund_id}/reconcile`
- `POST /api/v1/refunds/wechat/callback`

The M1 catalog/marketplace routes and M2 auth/session routes are compatibility
targets. M2.2 also carries the structured authorization/authority kernel used by
the current Python main line so M3 order writes do not fork the security model. FastAPI remains the reference implementation until the migration
cutover. Auth sessions intentionally share the existing PostgreSQL tables and
HS256 token contract so FastAPI- and Go-issued sessions remain interoperable.

Run the dual-runtime compatibility checks after starting both APIs against the
same database:

```bash
make go-parity
```

The parity target checks M1 read responses, M2 cross-runtime authentication,
M2.1 offering management, M3 order reads, M3.1 order creation, and M3.2
atomic provider claim:
FastAPI-issued access/refresh tokens must work through Go, Go-issued tokens must
work through FastAPI, and refresh-token reuse/logout revocations must be visible
from both runtimes. M3 parity creates/pays/claims an order through FastAPI, then
requires Go to read the exact same customer list, order detail, assigned provider,
OrderEvent evidence, and customer/player/platform access outcomes from shared
PostgreSQL truth. M3.2 additionally proves one-winner atomic claim under a
100-provider race. M3.3 owns provider start/finish. M3.4 owns customer confirmation and the
atomic settlement transaction: COMPLETED/SETTLED evidence, one Settlement,
provider/platform wallet credits and two ledger entries. Replayed or concurrent
confirmation must settle exactly once. M3.1 then gives Go ownership of one bounded write: order
creation. The parity gate verifies pooled and designated order economics,
self-order rejection, input/error compatibility, and the atomic
`orders + ORDER_CREATED + outbox_events` durable evidence set. M3.2 moves
claim ownership to Go with PostgreSQL compare-and-swap on
`status='MATCHING' AND version=expected_version`. Its gate races 100 distinct
eligible providers against one order and requires exactly one winner, one active
assignment, one `PLAYER_CLAIMED` OrderEvent and one matching OutboxEvent.

Marketplace list reads use a bounded batch strategy rather than copying the
reference implementation's per-player N+1 query pattern. The observable filter
order remains unchanged: candidate ordering/limit happens before game/rank
filtering.

## Package layout

```text
cmd/api/                 request-path process
cmd/worker/              background runtime
internal/app/            dependency wiring + HTTP server
internal/config/         env/files + fail-closed validation
internal/modules/        vertical business modules
  authz/                  structured policy, authority/admission + audit
internal/ports/          Auth/Payment/Refund external contracts
internal/platform/       pgx, redis, metrics, HTTP, state machine
internal/workers/outbox/  transactional outbox -> Redis Pub/Sub
```

## Branch rule

All Go child branches target `refactor/go-backend-foundation`. Do not merge
`feat/go-*` or `fix/go-*` directly into `main`.

## Migration rule

Do not translate SQLAlchemy models line-by-line. Each migrated module must keep
the existing database invariants and HTTP contract, then replace the Python
implementation behind the same behavior.

See `docs/go-backend-migration.md`.
