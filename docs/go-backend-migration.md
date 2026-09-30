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
- public provider offerings embedded in marketplace reads;
- read-only admin evidence.

Authenticated `/api/v1/player/offerings` remains in M2 because it depends on the PLAYER principal/session contract.

Why first: low write risk and easy response-level parity testing.

Acceptance: the CI parity job boots FastAPI and Go against the same seeded PostgreSQL/Redis state, then compares HTTP status and JSON payloads for the migrated routes.

### M2 - Auth/session

Port:

- WeChat code2Session provider;
- user binding with unique(openid) race recovery;
- access/refresh sessions using the existing HS256 claim contract;
- USER / PLAYER / PLATFORM roles recomputed from PostgreSQL;
- refresh rotation under row lock;
- descendant-family revocation on refresh-token reuse;
- logout and /auth/me compatibility.

Acceptance: FastAPI and Go run against the same database and signing key. CI
must prove both directions of interoperability: FastAPI-issued tokens are
accepted/rotated by Go, Go-issued tokens are accepted/rotated by FastAPI, and
revocation/reuse containment performed by either runtime is immediately visible
to the other.

### M2.2 - Authorization / authority convergence

Before order write-path migration, converge the Go runtime on the current
production authorization model introduced on `main`:

- secure role guards require session-backed principals;
- resource authorization returns structured `resource-authz.v2` decisions;
- decisions carry actor roles, session/request correlation and business evidence refs;
- bounded write authority uses `authority-envelope.v1` with canonical SHA256 digests;
- execution admission rejects state drift and bounded-write mismatch;
- authorization/admission evidence persists through the existing `outbox_events` audit channel.

The Go canonical envelope digest is pinned against a cross-language golden vector
produced by the Python implementation. This prevents the two runtimes from
quietly diverging on authority serialization while the migration is in progress.

M2.2 intentionally introduces the reusable policy/evidence kernel **before**
binding it to order/dispatch routes. M3 handlers must consume this kernel rather
than reintroducing endpoint-local ownership checks.

### M3 - Order/dispatch

Start with the read/evidence surface before moving write ownership:

- customer order list;
- order detail projection, including active/designated service player;
- OrderEvent evidence stream;
- customer / active-player / platform viewer parity.

The read slice is validated by writing the transaction through FastAPI against
the shared database, then requiring the Go runtime to produce the same HTTP
contract and authorization outcome.

Then port the mutation surface in bounded slices:

#### M3.1 - Order create

Go owns only `POST /api/v1/orders`:

- pooled SKU order creation;
- designated provider offering validation;
- cannot order one's own offering;
- price/platform-fee projection compatibility;
- atomic `Order + ORDER_CREATED OrderEvent + ORDER_CREATED OutboxEvent`.

Acceptance requires FastAPI to read Go-created orders/evidence from the shared
database with identical projections. Direct PostgreSQL assertions prove that a
successful create emits exactly one order event and one pending outbox event.

#### M3.2 - Atomic claim

Go owns the public-pool provider claim transition:

- PostgreSQL compare-and-swap on `MATCHING + expected_version`;
- provider eligibility and active SKU offering revalidated in the transaction;
- one ACTIVE assignment;
- atomic `PLAYER_CLAIMED` OrderEvent + Outbox evidence.

Acceptance runs 100 distinct eligible providers against one order and requires
exactly one winner and 99 `ORDER_ALREADY_ACCEPTED` conflicts.

#### M3.3 - Provider lifecycle

Go owns:

- `ACCEPTED -> IN_SERVICE` through `SERVICE_STARTED`;
- `IN_SERVICE -> FINISH_REQUESTED` through `FINISH_REQUESTED`;
- active-assignment ownership;
- deterministic order state-machine validation;
- row-locked lifecycle writes with version increment;
- atomic OrderEvent + Outbox evidence.

Repeated or out-of-order transitions must return the same 409 contract as the
Python reference and must not emit duplicate evidence.

#### M3.4 - Customer confirm / settlement

Go owns the money-sensitive confirmation transaction:

- customer owner check under an order row lock;
- idempotent replay after `SETTLED`;
- `FINISH_REQUESTED -> COMPLETED -> SETTLED`;
- atomic `USER_CONFIRMED_FINISH` and `SETTLEMENT_COMPLETED` evidence;
- one Settlement row per order;
- provider and platform wallets created-if-missing and locked before credit;
- wallet version increments;
- `PROVIDER_INCOME` and `PLATFORM_FEE` ledger entries.

The entire value flow commits once or rolls back once. Acceptance includes
cross-runtime replay plus a 20-request concurrent confirmation race and requires
one settlement, two ledger rows and one balance increment per wallet.

Customer/player/platform resource access must continue to preserve the same
structured authorization semantics as the Python reference.

#### M3.5 - Mock payment compatibility seam

Before moving real WeChat payment traffic, Go owns the existing dev/test
`POST /api/v1/orders/{order_id}/mock-pay` route through a dedicated payment
module.

The slice preserves the reference transaction contract:

- order row lock before payment creation;
- customer ownership;
- idempotency-key replay checked before current order status;
- one `PaymentTransaction(provider=MOCK,status=SUCCESS)`;
- `WAITING_PAYMENT -> PAID -> MATCHING`;
- `PAYMENT_SUCCESS` and `ORDER_ENTERED_MATCHING` OrderEvent + Outbox evidence;
- designated orders additionally create one USER assignment and transition
  `MATCHING -> ACCEPTED` with `DESIGNATED_PLAYER_ASSIGNED`;
- mock payment remains disabled in secure deployments.

Acceptance proves cross-runtime replay, a 20-request same-key exactly-once race,
and a 20-request distinct-key race with exactly one successful payment. Redis
pool membership remains reconstructable acceleration and is not part of payment
correctness.

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
