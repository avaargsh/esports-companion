# Golden Slice Acceptance

The v0.1 acceptance test is executable, not just documented.

Run:

```bash
make test
```

The test `test_golden_slice_e2e.py` verifies the complete marketplace path through HTTP APIs:

```text
Demo Bootstrap
  -> Create Order
  -> Mock Payment
  -> MATCHING / Order Pool
  -> Player Claim
  -> ACCEPTED
  -> Start
  -> IN_SERVICE
  -> Finish
  -> FINISH_REQUESTED
  -> Customer Confirm
  -> Settlement
  -> SETTLED
  -> Review
  -> Player Wallet + Ledger
```

Separate tests also verify:

- 100 concurrent claims produce exactly one winner.
- Mock payment is idempotent.
- Settlement is idempotent and writes exactly two ledger entries.
- Invalid state transitions are rejected.
