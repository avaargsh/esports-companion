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
go mod tidy
go test ./...
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

## Endpoints in foundation phase

- `GET /livez`
- `GET /readyz`
- `GET /metrics`
- `GET /api/v1/runtime`

Business routes remain on FastAPI until their compatibility tests are ported.

## Package layout

```text
cmd/api/                 process entrypoint
internal/app/            dependency wiring + HTTP server
internal/config/         env/files + fail-closed validation
internal/modules/        vertical business modules
internal/ports/          Auth/Payment/Refund external contracts
internal/platform/       pgx, redis, metrics, HTTP, state machine
```

## Migration rule

Do not translate SQLAlchemy models line-by-line. Each migrated module must keep
the existing database invariants and HTTP contract, then replace the Python
implementation behind the same behavior.

See `docs/go-backend-migration.md`.
