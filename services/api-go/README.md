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
```

Pool tuning:

```text
DATABASE_MAX_CONNS=32
DATABASE_MIN_CONNS=4
REDIS_POOL_SIZE=64
API_GO_HTTP_ADDR=:8080
SHUTDOWN_TIMEOUT_SECONDS=15
```

The loader accepts the current Python-style
`postgresql+psycopg://...` URL and normalizes it for pgx.

## Endpoints

- `GET /livez`
- `GET /readyz`
- `GET /metrics`
- `GET /api/v1/runtime`
- `GET /api/v1/games`
- `GET /api/v1/games/{game_id}/skus`
- `GET /api/v1/players`
- `GET /api/v1/players/{player_id}`

The M1 catalog/marketplace routes are compatibility targets. FastAPI remains the
reference implementation until the migration cutover.

Run the dual-runtime response check after starting both APIs against the same
database:

```bash
make go-parity
```

Marketplace list reads use a bounded batch strategy rather than copying the
reference implementation's per-player N+1 query pattern. The observable filter
order remains unchanged: candidate ordering/limit happens before game/rank
filtering.

## Package layout

```text
cmd/api/                 process entrypoint
internal/app/            dependency wiring + HTTP server
internal/config/         env/files + fail-closed validation
internal/modules/        vertical business modules
internal/ports/          Auth/Payment/Refund external contracts
internal/platform/       pgx, redis, metrics, HTTP, state machine
```

## Branch rule

All Go child branches target `refactor/go-backend-foundation`. Do not merge
`feat/go-*` or `fix/go-*` directly into `main`.

## Migration rule

Do not translate SQLAlchemy models line-by-line. Each migrated module must keep
the existing database invariants and HTTP contract, then replace the Python
implementation behind the same behavior.

See `docs/go-backend-migration.md`.
