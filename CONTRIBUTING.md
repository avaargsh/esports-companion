# Contributing

Thanks for improving esports-companion.

## Development principle

Keep the Golden Slice correct before adding horizontal features:

```text
Create -> Pay -> Match -> Claim -> Service -> Settle -> Ledger -> Review
```

## Architecture rules

- PostgreSQL is the durable source of truth.
- Redis is reconstructable acceleration state.
- Order status transitions go through the state-machine/domain service.
- Every successful transition writes an `OrderEvent`.
- Concurrent claim correctness is enforced by PostgreSQL, not by Redis locks.
- Money is stored as integer minor units.
- Payment and settlement must remain idempotent.
- Avoid splitting the modular monolith into microservices without a demonstrated boundary.

## Local checks

Backend:

```bash
make test
```

Mini Program:

```bash
make miniapp-build
```

Admin:

```bash
make admin-build
```

## Pull requests

A focused PR should include:

1. the behavior or invariant being changed;
2. tests for domain-sensitive changes;
3. migration changes when the persistent model changes;
4. documentation changes when APIs or setup change.

Do not mix unrelated refactors with feature work.
