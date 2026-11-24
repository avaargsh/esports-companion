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

The migration now uses `main` as its only integration line. The historical
`refactor/go-backend-foundation` branch is frozen and may be consulted as a
source of already-reviewed implementation, but it must not receive new feature
work or be merged wholesale.

Rules:

- create every new Go migration branch from the latest `main`;
- target every Go migration pull request at `main`;
- use `feat/go-*` for features and `fix/go-*` for fixes;
- keep each pull request to one semantic migration slice;
- preserve FastAPI as the executable reference until that slice passes
  cross-runtime parity;
- never merge the historical integration branch as a single large pull request;
- retire the historical branch after all accepted slices have landed on `main`.

The `API Go` workflow enforces the legacy-branch rejection and the target
branch rule for `feat/go-*` and `fix/go-*` pull requests.

## Mainline migration status (2026-11-24)

The following slices are already merged into `main`:

- M0 Go foundation: PR #85;
- M1 read-only catalog / marketplace parity: PR #86;
- M2 auth / session parity: PR #87;
- protected provider offerings: PR #88.

Authorization/authority convergence (M2.2), order/dispatch (M3),
payment/refund (M4), and background workers (M5) are separate acceptance
boundaries. The current migration sequence places the M2.2 authorization and
authority kernel before M3 order read/evidence, because order-level resource
authorization consumes that kernel. Implementation present only on the
historical branch is not considered mainline-complete until its own pull
request is merged.

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
- public provider offerings embedded in marketplace reads;
- read-only admin evidence.

Authenticated `/api/v1/player/offerings` remains in M2 because it depends on the PLAYER principal/session contract.

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

### M2.2 - Authorization / authority kernel

Port the reusable Go policy and evidence kernel before exposing order reads or
writes:

- `resource-authz.v2` structured owner/platform decisions;
- `authority-envelope.v1` canonical payload and SHA-256 digest;
- `authority-admission.v1` exact-state and bounded-write admission;
- append-only authorization/admission audit records through PostgreSQL
  `outbox_events`, written through the caller's `pgx.Tx` so evidence and the
  protected business mutation commit or roll back together.

Acceptance:

- Go digest matches the Python golden vector, including HTML-sensitive and Unicode payload values;
- canonical JSON preserves Python `sort_keys`, compact separators and `ensure_ascii=false` behavior;
- state comparison matches Python numeric and missing/null equality semantics;
- returned authority payload digest matches the exact serialized payload
  snapshot, including when timestamps are generated by the runtime;
- owner/platform allow and deny decisions retain their reason codes;
- state drift and bounded-write mismatch fail closed;
- audit records remain append-only and use the existing outbox schema.

This slice establishes the policy kernel only. Order handlers consume it in the
subsequent M3.0 PR; do not combine it with order writes or payment changes.

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
