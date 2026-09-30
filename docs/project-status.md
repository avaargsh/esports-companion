# Project Status — 2026-09-30

This page records the current engineering state of **esports-companion**. It is intentionally a status snapshot, not a marketing roadmap.

## Executive summary

The repository has moved beyond a UI demo into a transactional marketplace starter with a complete customer/provider/admin product slice.

The core path on `main` is now:

```text
Customer discovery / quick match
  -> order
  -> payment
  -> public claim or designated provider
  -> fulfillment
  -> customer confirm / dispute
  -> settlement or refund
  -> provider earnings
  -> withdrawal
  -> operator reconciliation
```

The remaining release risk is no longer basic CRUD or page completeness. The main gate is **real staging acceptance against WeChat and real-money boundaries**, especially the first low-value withdrawal end to end.

## Current milestone

**Milestone:** product slice complete enough for staging acceptance.

### Product surface

- WeChat Mini Program with customer and provider workspaces.
- Customer mental model reduced to Game -> Player -> Service -> Order -> Profile.
- Customer top-level navigation reduced to Home / Orders / Profile.
- Provider flow reduced to Claim -> Fulfill -> Earnings.
- Admin console reduced to Overview / Orders / Players / Finance / Configuration.
- Discovery supports both public marketplace matching and designated-provider booking.
- Withdrawal IDs and payout references are visible in the product/admin surface for acceptance and reconciliation.

### Transaction core

- Explicit order state machine with append-only `OrderEvent` history.
- PostgreSQL is the durable source of truth; Redis is reconstructable acceleration state.
- Atomic provider claim path with a 100-contender acceptance test requiring exactly one winner.
- Payment/cancel transitions are serialized.
- WeChat payment callback validates currency and payer identity.
- Payment, refund, dispute, settlement and withdrawal paths are idempotent.
- Disputes stop automatic settlement until resolved.
- Settlement ledger is the financial history; wallet balances are materialized query state.

### Authentication and authorization

- WeChat login adapter plus demo/mock mode.
- Short-lived access token + rotating refresh token.
- Server-side revocable sessions.
- Per-session revocation and logout-all.
- Refresh-token descendant/family containment on logout/reuse.
- USER / PLAYER / PLATFORM role boundaries.
- Privileged RBAC requires bearer sessions.
- Centralized order authorization policy.
- Resource authorization evidence is persisted for sensitive operations.
- Withdrawal writes are bound to an authority envelope and admission check against locked resource state.

### Operations and release engineering

- Admin work queues for players, disputes/refunds, withdrawals and settlements.
- Withdrawal reconciliation view combines status, payout reference, wallet state and matching ledger evidence.
- Transactional outbox + WebSocket realtime delivery.
- Production fail-fast configuration and file-backed secrets.
- Hardened non-root production container/Compose reference.
- Prometheus metrics and optional OpenTelemetry trace export.
- Backup/restore, ingress, staging-preflight and HTTP product-slice checks are part of the release process.
- The release checklist explicitly freezes further authority/evidence expansion until a real low-value withdrawal is completed end to end.

## Recent merged work

The most important recent merges on `main` are:

| PR | Area | Result |
| --- | --- | --- |
| #37 | Mini Program UX | Customer/provider experience redesign merged |
| #40–#44 | Auth/session/RBAC | Rotation containment, session management, revocation and bearer-bound privileged RBAC |
| #45–#49 | Authorization | Central policy, audit evidence, evidence v2, authority envelope and pre-write admission |
| #50 | Release gate | Product-slice release gate and change freeze |
| #51 | Withdrawal acceptance | Read-only verifier and staging runbook for first real withdrawal |
| #52 | Withdrawal traceability | Withdrawal IDs and payout references exposed to Mini Program/Admin |

The current `main` head at the time of this snapshot is:

```text
6f8fa9a feat(product): make withdrawal acceptance traceable (#52)
```

## Go backend migration track

A separate branch, `refactor/go-backend-foundation`, remains an active migration track rather than the production source of truth.

Completed work on that track includes:

- M1 catalog/marketplace reads;
- M1 hardening and integration checks;
- M2 auth/session runtime;
- protected provider offerings.

The FastAPI modular monolith on `main` remains authoritative until the Go track reaches explicit parity and acceptance gates. Avoid dual-source business truth during the migration.

## What is still not finished

### Required before calling the project production-ready

- Real WeChat Mini Program login in staging.
- Real low-value WeChat payment.
- Real refund path and provider reconciliation.
- Real low-value provider withdrawal:
  - request from the Mini Program;
  - frozen balance observed;
  - external payout completed;
  - the same payout reference recorded in Admin;
  - `make staging-withdrawal-acceptance ...` returns `PASS`.
- Production HTTPS/domain/callback configuration.
- Production-like database migration rehearsal.
- Backup/restore drill against a release backup.
- Alertmanager/notification routing and operational ownership.
- Final ingress/rate-limit review using the expected traffic profile.

### Deliberate non-goals for the current version

The project intentionally does not expand into social feed, voice rooms, gifts, guilds, agent/promoter systems, membership/coupon growth systems, CMS-heavy operations or premature microservice decomposition.

## Engineering assessment

The codebase is currently strongest as a **transactional vertical-slice reference implementation**:

```text
product flow
+ state-machine correctness
+ concurrency/idempotency
+ money ledger/reconciliation
+ session/RBAC
+ audit evidence
+ release/operations boundaries
```

The next milestone should therefore prioritize **real staging acceptance and operational proof**, not another round of architecture expansion.

## Next milestone

### M0 — real staging acceptance

1. Configure real WeChat staging credentials and HTTPS callback domains.
2. Run real login + low-value payment + refund acceptance.
3. Run the first low-value withdrawal end to end.
4. Record payout reference and verify reconciliation.
5. Complete backup/restore and alert-routing drills.
6. Only after the release gate passes, decide whether to continue the Go migration or add product features.

## Related documents

- [Product Simplification](product-simplification.md)
- [Release Checklist](release-checklist.md)
- [Operations](operations.md)
- [Architecture](architecture.md)
- [Production Readiness](production-readiness.md)
- [Real Withdrawal Acceptance](real-withdrawal-acceptance.md)
