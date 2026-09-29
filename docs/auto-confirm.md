# Automatic Finish Confirmation

A player finishing service moves the order into `FINISH_REQUESTED`.
The customer may confirm immediately. Otherwise a backend worker confirms the
order after the configured timeout.

Defaults:

```text
FINISH_CONFIRM_TIMEOUT_SECONDS=1800
ORDER_TIMEOUT_SCAN_SECONDS=30
ORDER_TIMEOUT_BATCH_SIZE=50
```

PostgreSQL is authoritative. Eligibility is derived from
`status=FINISH_REQUESTED` plus `finish_requested_at`; Redis timers are not
used for correctness.

Workers use `FOR UPDATE SKIP LOCKED` so multiple API instances can scan safely.
Manual confirmation and automatic confirmation share the same locked
`COMPLETED -> Settlement -> SETTLED` path. Settlement remains idempotent by its
existing per-order unique constraint.

Orders that moved to `DISPUTED` are automatically excluded because the worker
only selects `FINISH_REQUESTED`.
