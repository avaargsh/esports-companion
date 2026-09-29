# Refund Reconciliation

WeChat refund callbacks remain the primary asynchronous completion signal, but
the platform also reconciles provider truth through:

```text
GET /v3/refund/domestic/refunds/{out_refund_no}
```

For `REFUND_PROVIDER=wechat`, the API lifespan starts a lightweight
reconciliation worker. It scans durable `SUBMITTING` / `PROCESSING` refunds
older than the configured minimum age, queries WeChat by the persisted
merchant refund number, verifies the signed HTTP response, and feeds the result
back into the same `RefundService` state path used by callbacks.

Defaults:

```text
REFUND_RECONCILE_SCAN_SECONDS=60
REFUND_RECONCILE_MIN_AGE_SECONDS=30
REFUND_RECONCILE_BATCH_SIZE=20
```

The worker locks local state only while validating and applying transitions.
It releases the database transaction before the external WeChat query, then
re-locks and re-validates the aggregate before applying provider truth. This
keeps network latency outside database row-lock time.

A signed query response is not sufficient by itself: reconciliation also
matches `out_refund_no`, `out_trade_no`, the original WeChat
`transaction_id`, total amount, refund amount, and provider refund id before
moving the order to `REFUNDED`.

Operators may also force reconciliation through:

```text
POST /api/v1/admin/refunds/{refund_id}/reconcile
```


Provider refunds cannot use the manual-completion endpoint. For WeChat,
`REFUNDED` must come from verified callback or signed query state; the Admin
reconcile endpoint only triggers that verification.
