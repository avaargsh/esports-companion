# Project Status — 2026-11-24

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

## Current engineering baseline — 2026-11-24

Verified against GitHub at this snapshot:

- `main`: `18e98a1d` — Go validation is now part of the main Release Checklist Gate.
- `main` branch protection: not enabled (`protected=false`).
- GitHub Actions: no workflow runs or check-run contexts were observable for the inspected commits. Workflow configuration is not evidence of a successful run.
- Historical `refactor/go-backend-foundation`: 48 commits ahead / 71 behind `main`; source-only, not an integration target.

The mainline Go milestones already merged are PR #85 (M0 foundation), #86 (M1 catalog/marketplace), #87 (M2 auth/session), #88 (protected offerings), #104 (mainline migration policy), and #105 (Go checks in the release gate).

PR #106 is the in-progress M2.2 authorization/authority kernel slice. It is not merged and must not be treated as part of the current mainline until its Go checks and parity evidence pass.

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
| #85 | Go foundation | Minimal Go API runtime and platform foundation merged |
| #86 | Go M1 | Read-only catalog and marketplace parity merged |
| #87 | Go M2 | Auth/session parity merged |
| #88 | Go offerings | Protected provider offerings merged |
| #104 | Go migration governance | Mainline-only migration policy and legacy branch guard merged |
| #105 | Go CI gate | Go validation added to the main release checklist gate |

The current `main` head at the time of this snapshot is:

```text
18e98a1 ci: require Go backend validation in release gate (#105)
```

## Go backend migration track

The Go migration now uses `main` as its only integration line. The historical
`refactor/go-backend-foundation` branch is frozen and source-only; it is
currently 48 commits ahead / 71 commits behind and must not be merged wholesale.

Mainline Go slices already merged:

- M0 Go foundation — PR #85;
- M1 read-only catalog / marketplace parity — PR #86;
- M2 auth/session parity — PR #87;
- protected provider offerings — PR #88;
- mainline-only migration policy — PR #104;
- Go module, formatting, vet, race-test and build checks in the Release Gate — PR #105.

Current migration state:

- M2.2 authorization / authority / evidence kernel — PR #106, open and not yet
  accepted into `main`;
- M3 order read/evidence and subsequent order write paths — not yet on `main`;
- M4 payment/refund and M5 outbox/realtime/workers — not yet on `main`.

The next sequence is M2.2 authorization/evidence, M3.0 order read/evidence,
M3.1 order create, M3.2 atomic claim, M3.3 provider lifecycle, M3.4 settlement,
M3.5 mock payment, then M4 and M5. Keep FastAPI as the executable reference
until each semantic slice passes cross-runtime PostgreSQL parity.

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
6. Continue Go migration through separate main-targeting semantic PRs; do not cut traffic over until cross-runtime parity, staging acceptance and rollback evidence pass.

## Related documents

- [Product Simplification](product-simplification.md)
- [Release Checklist](release-checklist.md)
- [Operations](operations.md)
- [Architecture](architecture.md)
- [Production Readiness](production-readiness.md)
- [Real Withdrawal Acceptance](real-withdrawal-acceptance.md)
