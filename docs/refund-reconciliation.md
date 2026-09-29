# Refund Reconciliation

WeChat refund callbacks remain the primary asynchronous completion signal, but
the platform also reconciles provider truth through:

```text
GET /v3/refund/domestic/refunds/{out_refund_no}
```

For `REFUND_PROVIDER=wechat`, the API lifespan starts a lightweight
reconciliation worker. It scans durable `SUBMITTING` / `PROCESSING` refunds
older than the configured scan interval, queries WeChat by the persisted
merchant refund number, verifies the signed HTTP response, and feeds the result
back into the same `RefundService` state path used by callbacks.

Defaults:

```text
REFUND_RECONCILE_SCAN_SECONDS=60
REFUND_RECONCILE_BATCH_SIZE=20
```

Multiple instances are safe against duplicate financial effects because the
refund row is locked before applying provider state and `Order REFUNDED` is
still reached only through the idempotent refund aggregate. A second worker
that waited on the lock re-checks `updated_at` and skips a just-reconciled row.

Operators may also force reconciliation through:

```text
POST /api/v1/admin/refunds/{refund_id}/reconcile
```
