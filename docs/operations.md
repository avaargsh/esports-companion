# Operations Console and Money Operations

The v0.4 operations surface is intentionally a work queue, not a second source of truth.

Operators act on domain APIs; they do not edit order, wallet, settlement or refund rows directly.

## Operator work queues

The Admin console exposes:

- provider application review;
- player skill/evidence review;
- service catalog management;
- order lookup;
- dispute/refund handling;
- withdrawal review;
- settlement inspection.

## Dispute handling

Open disputes are handled through one of two domain actions:

```text
OPEN dispute
  -> release to provider
     -> settlement path resumes

  -> approve refund
     -> Refund entity
     -> provider submit/reconcile
     -> terminal refund state
```

Operational rules:

- do not manually mutate the order status;
- do not release provider funds while a dispute is open;
- provider refund state is authoritative only after backend provider verification;
- use the refund reconcile action when provider state is uncertain;
- retain order chat and OrderEvent evidence as the operator's audit context.

## Withdrawal handling

Current payout mode is `MANUAL`.

Player request:

```text
available balance
  -> withdrawal request
  -> available - amount
  -> frozen + amount
  -> PENDING
```

Operator completion:

```text
real external payout completed
  -> record real external payout / transfer reference
  -> confirm paid
  -> frozen - amount
  -> COMPLETED
  -> ledger entry
```

Operator rejection:

```text
PENDING
  -> reject with reason
  -> frozen - amount
  -> available + amount
  -> REJECTED
  -> ledger entry
```

The console requires a real external payout reference and a confirmation step. **Never mark a withdrawal COMPLETED before the external payout actually succeeded.** A completed payout reference is treated as immutable audit evidence.

## Daily operating routine

A practical minimum routine for a small deployment:

1. review pending player and skill verification;
2. clear OPEN disputes;
3. check non-terminal refunds and reconcile stale provider state;
4. process PENDING withdrawals;
5. inspect failed/stuck payment, refund, withdrawal and outbox alerts;
6. verify backup/restore and health/metrics status before high-traffic periods.

## Incident boundaries

When money state looks inconsistent:

- stop manual completion actions;
- preserve order/payment/refund/withdrawal IDs;
- inspect Ledger and provider transaction IDs;
- reconcile provider facts before changing platform state;
- never "fix" a wallet by directly editing the balance.

PostgreSQL durable state and Ledger history remain the accounting evidence.

## Current limitations

The v0.4 Admin console is an internal operations surface.

- It does not implement a full enterprise SSO/IdP login page.
- Secure deployments require a PLATFORM Bearer operator session.
- Withdrawal payout is manual.
- No recommendation-ranking operations UI exists yet.
- No bulk marketing or CRM workflow is included.

These limits are intentional; they keep the operations layer aligned with the existing transactional core instead of creating another workflow engine.


## Order evidence view

Order lookup and dispute handling both link to the same read-only evidence drawer.

It combines:

- current order status and version;
- customer total, provider amount and platform fee;
- assigned/designated provider identity;
- append-only OrderEvent history;
- complete order-scoped chat history available to PLATFORM.

PLATFORM access to chat is intentionally read-only. Operators can inspect
evidence for support and dispute resolution, but cannot impersonate a USER or
PLAYER by sending into the order chat.


## Withdrawal reconciliation view

Each withdrawal links to a read-only reconciliation drawer that combines:

- withdrawal status and external payout reference;
- current Wallet available/frozen balances and version;
- only the Ledger entries whose `biz_type=WITHDRAWAL` and `biz_id` matches the withdrawal.

This view is for reconciliation and incident analysis. Operators still must not edit wallet balances or ledger rows directly.


## SLA-driven operations queue

The Admin landing page is an exception queue derived from PostgreSQL durable state.
It does not scrape Prometheus to decide business state.

Reference categories:

- transactional Outbox pending longer than 60 seconds;
- Refund in PENDING / SUBMITTING / PROCESSING longer than 15 minutes;
- Withdrawal PENDING longer than 1 hour;
- Dispute OPEN / RESOLVING longer than 24 hours;
- Order FINISH_REQUESTED older than the configured auto-confirm timeout plus scan grace.

The first four thresholds intentionally mirror the reference Prometheus alert rules.
The FINISH_REQUESTED threshold is derived from the runtime configuration:

```text
FINISH_CONFIRM_TIMEOUT_SECONDS + ORDER_TIMEOUT_SCAN_SECONDS
```

The queue returns workload summaries for all active items and lists only SLA breaches.
Operators can jump from a queue item directly to Order Evidence or Withdrawal Evidence.

Prometheus remains the alerting surface; the Admin queue is the human work surface.
Neither is a source of business truth.
