# Core invariants

1. PostgreSQL owns durable order truth.
2. Status changes only through the order domain service.
3. Every successful transition writes OrderEvent and OutboxEvent.
4. At most one ACTIVE OrderAssignment exists per order.
5. Only MATCHING orders may be claimed.
6. Payment and settlement are idempotent.
7. Monetary values are integer minor units.
8. Ledger history is immutable; balance is materialized state.
