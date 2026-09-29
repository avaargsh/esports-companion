# Go backend migration

## Decision

Refactor the backend toward a Go modular monolith while keeping the existing
FastAPI implementation as the executable compatibility reference during the
migration.

The target is a reusable transactional service foundation, not an esports-only
rewrite and not an early microservice split.

```text
Mini Program / Admin
        |
      /api/v1
        |
  compatibility boundary
      /       \
FastAPI       Go API
(reference)   (migration target)
       \       /
       PostgreSQL
       durable truth
           |
         Redis
   reconstructable acceleration
```

## Branch integration policy

The Go migration has its own integration line:

```text
refactor/go-backend-foundation
        ^
        |
   PR only from
 feat/go-* / fix/go-*
```

Rules:

- Go feature/fix branches are created from `refactor/go-backend-foundation`;
- their pull requests target `refactor/go-backend-foundation`, never `main`;
- do not merge a child Go branch directly into the Python/main line;
- the Go integration branch is the only place where migration slices are composed;
- retargeting or merging the Go integration branch outward happens only as an explicit cutover/release action.

This keeps unfinished migration work isolated while still allowing small reviewable Go PRs.

## Non-negotiable invariants

The Go path inherits the current backend rules:

1. PostgreSQL remains the source of truth for order, money, session and audit state.
2. Redis cannot become durable truth.
3. State transitions are deterministic and write evidence.
4. Claim/assignment correctness comes from PostgreSQL conditional writes/constraints.
5. Payment success comes only from verified provider facts.
6. Payment/refund/settlement/withdrawal paths remain idempotent.
7. Ledger is money history; wallet is materialized query state.
8. Refresh-token reuse contains the descendant session family.
9. Provider callbacks must be signature-verified before durable mutation.

## Target package model

```text
cmd/api
  |
internal/app
  +-- config
  +-- platform
  |     +-- httpx
  |     +-- postgresx
  |     +-- redisx
  |     +-- metrics
  |     +-- statemachine
  |
  +-- ports
  |     +-- AuthProvider
  |     +-- PaymentProvider
  |     +-- RefundProvider
  |
  +-- modules
        +-- auth
        +-- catalog
        +-- order
        +-- dispatch
        +-- payment
        +-- refund
        +-- wallet
        +-- dispute
        +-- review
        +-- realtime
        +-- admin
```

Each module should converge on:

```text
transport -> application service -> domain -> repository/ports
```

Handlers do protocol work. Application services own use cases. Domain code owns
state rules. Repositories own SQL. External SDKs stay behind ports.

## Migration order

### M0 - Foundation

Current branch:

- Go process/runtime;
- config and secret-file compatibility;
- pgx / Redis pools;
- liveness/readiness;
- Prometheus HTTP metrics;
- structured access logs;
- reusable deterministic state machine;
- provider port contracts;
- non-root static container;
- independent Go CI.

No business traffic is cut over at M0.

### M1 - Read-only modules

Port first:

- catalog;
- marketplace discovery;
- provider offerings;
- read-only admin evidence.

Why first: low write risk and easy response-level parity testing.

Acceptance: the CI parity job boots FastAPI and Go against the same seeded PostgreSQL/Redis state, then compares HTTP status and JSON payloads for the migrated routes.

### M2 - Auth/session

Port:

- WeChat code2Session provider;
- user binding;
- access/refresh sessions;
- USER / PLAYER / PLATFORM roles;
- refresh rotation + descendant-family revocation on token reuse.

Acceptance: existing auth contract tests become implementation-neutral.

### M3 - Order/dispatch

Port:

- order state machine;
- OrderEvent append;
- designated provider;
- atomic claim;
- lifecycle transitions.

Acceptance: PostgreSQL concurrency test still runs 100 claims against one order
and produces exactly one winner.

### M4 - Payment/refund

Port last among request-path modules:

- WeChat JSAPI create;
- signed callback verification;
- callback replay recovery;
- payer/currency/order binding;
- refund create/callback/query reconciliation.

No client callback may advance durable payment state.

### M5 - Background runtime

Port:

- transactional outbox publisher;
- order timeout scanner;
- refund reconciliation;
- operational metrics worker.

Workers must use the same durable tables and idempotency rules; do not introduce
a parallel queue truth during migration.

### M6 - Cutover

Only after parity and load tests:

1. route a small read-only percentage to Go;
2. cut read paths;
3. cut auth;
4. cut order/dispatch;
5. cut payment/refund;
6. cut workers;
7. remove FastAPI only after rollback window expires.

## Performance policy

Go is chosen to reduce runtime overhead and make concurrency/backpressure easier
to control, not to justify unnecessary services.

Measure before splitting:

- request throughput and p50/p95/p99;
- allocations/op and heap growth;
- goroutine count;
- pgx pool acquire latency/saturation;
- Redis pool waits;
- PostgreSQL lock/transaction latency;
- callback and outbox backlog age.

The likely bottleneck for transactional paths remains PostgreSQL contention and
external provider latency, not the HTTP router.

## Explicit non-goals

- no database rewrite;
- no Redis-as-truth optimization;
- no Kafka/NATS merely because the backend is Go;
- no per-domain microservices before profiling proves the boundary;
- no breaking mini-program/admin API redesign during language migration.
