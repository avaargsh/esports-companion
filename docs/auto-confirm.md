# Finish Auto-confirm

A completed service should not remain in `FINISH_REQUESTED` forever when the customer does not respond.

Default policy:

```text
FINISH_REQUESTED
  + 30 minutes without customer action
  -> AUTO_CONFIRM_FINISH
  -> COMPLETED
  -> existing SettlementService
  -> SETTLED
```

Configuration:

```text
FINISH_CONFIRM_TIMEOUT_SECONDS=1800
ORDER_TIMEOUT_SCAN_SECONDS=30
```

## Correctness

The scanner discovers due order IDs, then locks and re-validates each order before changing state. Only an order that is still `FINISH_REQUESTED` and still past its deadline may be auto-confirmed.

This protects against races with:

- customer confirmation;
- dispute opening;
- administrative state changes;
- multiple timeout scanners.

Settlement remains idempotent through the existing unique settlement invariant.

v0.2 uses an in-process scanner to keep the open-source deployment small. A larger deployment can move the same service method into a dedicated scheduler/worker without changing order semantics.
