# Alert Runbook

These alerts are reference starting points. Tune thresholds against observed
traffic, business SLA/SLO and operator response times.

## API down

**Alert:** `EsportsCompanionApiDown`

1. Check ingress `/readyz` and API container health.
2. Check PostgreSQL and Redis health.
3. Inspect the most recent deployment/commit SHA.
4. Roll back application code if readiness failed immediately after a release.
5. Do not bypass PostgreSQL correctness checks to restore traffic.

## High 5xx ratio

**Alert:** `EsportsCompanionHigh5xxRatio`

1. Group structured logs by route/status and correlate `trace_id`.
2. Check PostgreSQL saturation/errors and provider callback failures.
3. Check whether one route dominates errors.
4. If payment/refund callbacks are failing, preserve raw provider facts and
   rely on reconciliation rather than manually forcing order state.

## High p99 latency

**Alert:** `EsportsCompanionHighP99Latency`

1. Split histogram p99 by route.
2. Check DB latency/locks, Redis latency, and external WeChat calls.
3. Inspect traces for the slow route.
4. Treat provider calls separately from local DB/state-machine latency.

## Operational metrics scan failed

**Alert:** `EsportsCompanionOperationalMetricsScanFailed`

The read-only PostgreSQL scan itself is failing. Check database connectivity,
credentials and schema compatibility. This alert means business-aging gauges
may be stale; do not assume a zero gauge is healthy until scanning recovers.

## Outbox stuck

**Alert:** `EsportsCompanionOutboxStuck`

1. Check the outbox publisher task logs.
2. Verify WebSocket publishing errors are not crashing the worker.
3. Query oldest `outbox_events.status='PENDING'` rows.
4. Do not delete pending events as a first response. Restore the publisher,
   then let events publish idempotently.

## Refund stuck

**Alert:** `EsportsCompanionRefundStuck`

1. Inspect Refund status and `out_refund_no`.
2. Check WeChat refund callback verification logs.
3. Run the existing provider query reconciliation path.
4. Compare merchant order/refund IDs and amounts before any manual action.
5. Never credit the provider wallet while the order is on the refund path.

## Withdrawal stuck

**Alert:** `EsportsCompanionWithdrawalStuck`

1. Check the pending Withdrawal and frozen wallet balance.
2. Verify whether the manual/provider transfer actually occurred.
3. Complete or reject through `WithdrawalService`; do not mutate wallet
   balances directly.
4. Confirm corresponding ledger history after resolution.

## Dispute aging

**Alert:** `EsportsCompanionDisputeAging`

1. Review dispute reason/evidence and held amount.
2. Confirm no settlement occurred after entering `DISPUTED`.
3. Resolve through provider-release or customer-refund paths only.
4. Treat the default 24-hour threshold as a reference policy, not a universal
   customer-support SLA.


## Finish request overdue

**Alert:** `EsportsCompanionFinishRequestOverdue`

1. Open the Admin operations queue and inspect the affected order Evidence.
2. Verify `finish_requested_at`, current order state and recent OrderEvent history.
3. Check the timeout worker logs and whether the scheduler loop is running.
4. Confirm there is no open dispute before any completion action.
5. Do not mutate the order row manually; restore the existing auto-confirm path or use the supported domain action.
